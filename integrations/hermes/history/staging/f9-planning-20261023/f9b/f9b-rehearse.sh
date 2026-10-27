#!/usr/bin/env bash
# F9-B LOCAL WSL MIRROR rehearsal (refused on lilith-dev-01). Synthetic Groq only; no real provider, no DEV/PROD.
# Candidate f293e72-f9b1: canary messages through normal, failure, restart and OPERATE-profile scenarios, then a
# byte scan of the whole mirror filesystem + every journal. Only the Hermes conversation store (state.db/-wal) may
# hold the canary afterwards; every other hit is a LEAK. Mirror-only synthetic ledger RESETs are used between
# scenarios (the DEV budget is never touched).
set -uo pipefail
[[ $(hostname) != lilith-dev-01 ]] || { echo "refused on lilith-dev-01"; exit 1; }
W=/root/f9b; REL=f293e72-f9b1; PKGN=hermes-gateway-dev-$REL; P=/var/tmp/f8/$PKGN; F9A=/root/f9a/build/pkg
HH=/home/lilith/.hermes-dev; R=/opt/hermes-gateway-dev/current; SY=/root/f8r4/synth; B=/var/backups/hermes-gateway-dev
L=/var/lib/private/hermes-provider-gate-dev/ledger.log; CAN=F9B-CANARY
MARK=F8R3-SYNTHETIC-PROVIDER-REPLY; RES=$W/f9b-rehearsal.tsv; : > $RES; EV=$W/ev; rm -rf $EV; mkdir -p $EV
rec() { printf '%s\t%s\t%s\n' "$1" "$2" "$3" | tee -a "$RES"; }
TOK() { grep '^LILITH_OS_TOKEN=' $HH/.env | cut -d= -f2; }
turn() { curl -s -m 150 -o $EV/turn.json -w '%{http_code}' -H "X-LILITH-OS-Token: $(TOK)" -H 'Content-Type: application/json' \
          -d "{\"message\":\"$1\",\"session\":\"$2\"}" http://127.0.0.1:9901/; }
reply() { python3 -c 'import json;d=json.load(open("'$EV'/turn.json"));print(d.get("state"),"|"," ".join((d.get("reply") or "")[:70].split()))' 2>/dev/null || echo "no-json"; }
mode() { echo "$1" > $SY/mode; }
reset_ledger() { bash $R/bin/gate_budget.sh reset --owner-approved "mirror-only-f9b-$1" >/dev/null 2>&1; }
dumps() { ls $HH/sessions/request_dump_* 2>/dev/null | wc -l; }
start_ready() {  # readiness of THIS start: gate START since now + Hermes ready line after the current log end
  local since n0; since=$(date '+%Y-%m-%d %H:%M:%S'); n0=$(cat $HH/logs/gateway.log 2>/dev/null | wc -l)
  systemctl start hermes-gateway-dev
  for _ in $(seq 1 120); do
    ss -Hltn 'sport = :9901' | grep -q . && ss -Hltn 'sport = :9911' | grep -q . \
      && journalctl --namespace=hermes-gateway-dev -u hermes-provider-gate-dev --since "$since" -o cat --no-pager | grep -q '"decision": "START"' \
      && tail -n +$(( n0 + 1 )) $HH/logs/gateway.log 2>/dev/null | grep -q 'Press Ctrl+C to stop' && return 0
    sleep 1; done; return 1; }
wait_gw_ready_after() {  # <log line count> : Hermes ready line after that point (auto-restart by systemd)
  for _ in $(seq 1 120); do tail -n +$(( $1 + 1 )) $HH/logs/gateway.log 2>/dev/null | grep -q 'Press Ctrl+C to stop' \
    && ss -Hltn 'sport = :9901' | grep -q . && return 0; sleep 1; done; return 1; }
scenario() {  # <id> <session> : one canary turn, record code/state and dump count
  local c r; c=$(turn "$CAN-$1 synthetic scenario text: reply with one short sentence." "$2"); r=$(reply)
  rec "S-$1" INFO "http=$c reply=[$r] request_dumps=$(dumps)"; }

echo "#### S0 mirror baseline"
MIRROR_SET_UP=0
if [[ ! -f /etc/systemd/system/lilith-memory-broker.service ]]; then
  bash /root/f8r2/mirror/mirror_setup.sh /root/f8r2/repo /root/f8hd/build/pkg/uv/uv > $EV/mirror-setup.log 2>&1 \
    && MIRROR_SET_UP=1 && rec mirror-setup PASS "stand-ins up" || { rec mirror-setup FAIL "$(tail -3 $EV/mirror-setup.log)"; exit 1; }
fi
for rb in /var/tmp/f8/*/bin/rollback.sh; do [[ -x $rb ]] && bash $rb remove >/dev/null 2>&1; done
systemctl daemon-reload
[[ -d $B ]] && mkdir -p $W/old && mv $B $W/old/backups-$(date +%s)
python3 -I /root/f8r4/amend/patch_fake_groq.py /root/f8r4/mirror/fake_groq.py >/dev/null
python3 -I /root/f8r4/amend/patch_fake_groq_msgs.py /root/f8r4/mirror/fake_groq.py >/dev/null
bash /root/f8r4/mirror/synthprov.sh up >/dev/null
rm -rf /var/tmp/f8 && install -d -m 0700 /var/tmp/f8 && cp $W/out/$PKGN.tar.gz* /var/tmp/f8/
(cd /var/tmp/f8 && sha256sum -c $PKGN.tar.gz.sha256 >/dev/null && tar -xzf $PKGN.tar.gz && cd $PKGN && sha256sum --quiet -c MANIFEST.sha256) \
  && rec G-2 PASS "f9b1 $(cut -c1-16 /var/tmp/f8/$PKGN.tar.gz.sha256) + MANIFEST" || { rec G-2 FAIL ""; exit 1; }
systemctl start lilith-memory-broker.service lilith-authority-dev.service lilith-recovery-witness.service lilith-os-api-dev.service; sleep 4
bash $P/bin/observe_host.sh $EV/M0 >/dev/null
bash $P/bin/dr5_check.sh $EV/dr5-M0.txt > $EV/dr5-M0-check.txt && rec M0-DR5 PASS "$(tail -1 $EV/dr5-M0-check.txt | cut -c1-40)" || { rec M0-DR5 FAIL ""; exit 1; }

echo "#### install + G-4 (F7, F9-A, F9-B suites) + NEG control (F9-B tests on the F9-A tree)"
bash $P/bin/backup_pre_install.sh >/dev/null; PRE=$(ls -d $B/pre-* | tail -1)
F8_SIM=1 bash $P/bin/install.sh > $EV/install.log 2>&1 && grep -q "F8_INSTALL_STAGED $REL" $EV/install.log && rec G-3 PASS staged || { rec G-3 FAIL "$(tail -2 $EV/install.log)"; exit 1; }
suite() {  # <tag> <src dir> <home dir> <dev cfg> <operate cfg>
  local T; T=$(mktemp -d /var/tmp/f9b-g4-XXXXXX)
  if [[ $2 == /root/* ]]; then cp -a "$2" $T/hermes-agent; else ln -s "$2" $T/hermes-agent; fi
  mkdir $T/hermes-home-dev $T/tests
  cp -a "$3/lilith_router" "$3/plugins" $T/hermes-home-dev/
  cp $P/tests/f7-home/config.yaml $T/hermes-home-dev/; cp $P/tests/f7-home/router.yaml $T/hermes-home-dev/lilith_router/
  cp $P/tests/test_f7_offline.py $P/tests/test_f9a_offline.py $P/tests/test_f9b_offline.py $T/tests/
  cp "$4" $T/dev.yaml; cp "$5" $T/operate.yaml; chown -R lilith:lilith $T; chmod 700 $T
  local E="env -i PATH=/usr/bin:/bin HOME=$T PYTHONUNBUFFERED=1 F9A_DEV_CONFIG=$T/dev.yaml F9B_DEV_CONFIG=$T/dev.yaml F9B_OPERATE_CONFIG=$T/operate.yaml"
  for t in f7 f9a f9b; do runuser -u lilith -- $E $R/venv/bin/python -B $T/tests/test_${t}_offline.py > $EV/$1-$t.log 2>&1; done
  rm -rf -- "$T"; }
suite G4 $R/src $P/home $P/home/config.yaml $P/profiles/operate/config.yaml
for t in f7 f9a f9b; do grep -q '^OK$' $EV/G4-$t.log && rec G-4-$t PASS "$(grep '^Ran ' $EV/G4-$t.log) OK" \
  || rec G-4-$t FAIL "$(grep -E '^(FAIL|ERROR):|^Ran |^FAILED' $EV/G4-$t.log | tr '\n' ' ' | cut -c1-300)"; done
suite NEG $F9A/src $F9A/home $F9A/home/config.yaml $F9A/profiles/operate/config.yaml
neg=$(grep -E '^(FAIL|ERROR):' $EV/NEG-f9b.log | sed 's/^[A-Z]*: //; s/ (.*//' | sort | paste -sd' ')
want="test_both_profiles_disable_profile_build test_conversation_turn_log_has_size_not_text test_dump_file_written_on_error_is_content_free test_inbound_message_log_has_sizes_not_text test_sanitizer_keeps_diagnostics_drops_content"
grep -q 'PermissionError' $EV/NEG-f9b.log && rec NEG-control INVALID "environment error"
[[ $neg == "$want" ]] && rec NEG-control DETECTED "on the F9-A tree exactly the 5 F9-B behaviour tests fail: $neg" || rec NEG-control UNEXPECTED "[$neg]"

echo "#### G-5, G-6, G-6b"
bash $P/bin/provision_console_token.sh >/dev/null
printf '%s\n' "$(cat $SY/synthetic-key)" | script -qec "bash $P/bin/provision_provider_key.sh" /dev/null > $EV/key.log 2>&1
$R/venv/bin/python -I -B $R/bin/verify_release.py --full > $EV/g5c.log 2>&1 && rec G-5c PASS "$(tail -1 $EV/g5c.log)" || { rec G-5c FAIL "$(tail -3 $EV/g5c.log)"; exit 1; }
start_ready && rec G-6 PASS ready || { rec G-6 FAIL ""; exit 1; }
bash $R/bin/sandbox_probe.sh > $EV/probe.txt 2>&1 && rec G-6b-sandbox PASS "$(tail -1 $EV/probe.txt)" || rec G-6b-sandbox FAIL "$(grep FAIL $EV/probe.txt | tr '\n' ' ')"
bash $R/bin/gate_probe.sh > $EV/gprobe.txt 2>&1 && rec G-6b-gate PASS "$(tail -1 $EV/gprobe.txt)" || rec G-6b-gate FAIL ""

echo "#### canary scenarios (VALIDATE profile, logging INFO)"
mode ok;       reset_ledger c1; scenario C1-normal f9b-c1
mode fail500;  reset_ledger c2; scenario C2-upstream500 f9b-c2
mode ratelimit; reset_ledger c3; scenario C3-ratelimit429 f9b-c3
mode reset;    reset_ledger c4; scenario C4-stream-cut f9b-c4
mode ok;       systemctl stop hermes-provider-gate-dev; scenario C5-gate-down f9b-c5
gsince=$(date '+%Y-%m-%d %H:%M:%S'); systemctl start hermes-provider-gate-dev
for _ in $(seq 1 90); do journalctl --namespace=hermes-gateway-dev -u hermes-provider-gate-dev --since "$gsince" -o cat --no-pager | grep -q '"decision": "START"' && break; sleep 1; done
reset_ledger c6; for i in 1 2 3 4 5; do turn "filler turn $i without the marker" f9b-fill >/dev/null; done
rec C6-pre INFO "budget before C6: $(bash $R/bin/gate_budget.sh show | cut -c1-140)"
scenario C6-budget-exhausted f9b-c6
echo "-- C7: SIGKILL the gateway while a canary request is in flight; systemd restarts it; continue session c1"
mode slow; reset_ledger c7; n0=$(wc -l < $HH/logs/gateway.log)
( turn "$CAN-C7-inflight synthetic text that is in flight when the gateway is killed." f9b-c7 >/dev/null ) &
sleep 6; kill -9 "$(systemctl show -p MainPID --value hermes-gateway-dev)"; rec C7-kill INFO "SIGKILL sent; NRestarts before restart: $(systemctl show hermes-gateway-dev -p NRestarts --value)"
wait_gw_ready_after "$n0" && rec C7-restart PASS "auto-restarted (NRestarts=$(systemctl show hermes-gateway-dev -p NRestarts --value))" || { start_ready; rec C7-restart INFO "manual start needed"; }
mode ok; reset_ledger c7b; scenario C7-after-restart f9b-c1
echo "-- C8: SIGTERM restart while a canary request is in flight"
mode slow; reset_ledger c8
( turn "$CAN-C8-inflight synthetic text that is in flight during a SIGTERM restart." f9b-c8 >/dev/null ) &
sleep 6; n0=$(wc -l < $HH/logs/gateway.log); systemctl restart hermes-gateway-dev; mode ok
wait_gw_ready_after "$n0" && rec C8-restart PASS "restarted during an in-flight request; ready" || rec C8-restart FAIL ""
reset_ledger c8b; scenario C8-after-restart f9b-c8

echo "#### OPERATE profile (logging WARNING) + C9 normal / failure"
n0=$(wc -l < $HH/logs/gateway.log)
# Known F8 unit property (not F9): StartLimitBurst=3 / 300 s; the C7 SIGKILL restart + C8 restart + the profile's own
# stop/start exceed it ("Start request repeated too quickly"). Explicit, recorded operator step in the mirror:
rec start-limit INFO "NRestarts=$(systemctl show hermes-gateway-dev -p NRestarts --value); operator step: systemctl reset-failed hermes-gateway-dev"
systemctl reset-failed hermes-gateway-dev
F8_SIM=1 bash $P/bin/apply_profile.sh operate > $EV/operate.log 2>&1 && rec operate-profile PASS "$(tail -1 $EV/operate.log)" || rec operate-profile FAIL "$(tail -3 $EV/operate.log | tr '\n' ' ')"
cmp -s $HH/config.yaml $P/profiles/operate/config.yaml && grep -q '^  level: WARNING' $HH/config.yaml && grep -A1 '^onboarding:' $HH/config.yaml | grep -q 'profile_build: "off"'   && rec operate-config PASS "installed config == OPERATE profile: logging WARNING, profile_build \"off\"" || rec operate-config FAIL "$(grep -E '^  level:|profile_build' $HH/config.yaml | tr '
' ' ')"
wait_gw_ready_after "$n0" || start_ready
mode ok;      reset_ledger c9; scenario C9-operate-normal f9b-c9
mode fail500; reset_ledger c9b; scenario C9-operate-upstream500 f9b-c9b
mode ok

echo "#### scans (gateway stopped so every log is flushed)"
sleep 70   # let the two slow synthetic upstream calls (75 s) finish so their gate records exist before the scan
bash $R/bin/rollback.sh stop > $EV/stop.log 2>&1
grep -rlaF "$CAN" /home /var/backups/hermes-gateway-dev /var/tmp /tmp /var/log /opt/hermes-gateway-dev /etc /var/lib /run /srv 2>/dev/null | sort -u > $EV/scan-files.txt
allowed="$HH/state.db $HH/state.db-wal $HH/state.db-shm"
leaks=$(while read -r f; do [[ " $allowed " == *" $f "* ]] || echo "$f"; done < $EV/scan-files.txt)
rec SCAN-files INFO "files containing the canary: $(paste -sd' ' $EV/scan-files.txt)"
[[ -z $leaks ]] && rec SCAN-filesystem PASS "only the conversation store holds the canary" || rec SCAN-filesystem FAIL "LEAKS: $(echo $leaks)"
jn=$(journalctl --namespace=hermes-gateway-dev -o cat --no-pager | grep -c "$CAN"); js=$(journalctl -o cat --no-pager | grep -c "$CAN")
ja=$(journalctl -u lilith-os-api-dev -o cat --no-pager | grep -c "$CAN")
[[ $jn -eq 0 && $js -eq 0 ]] && rec SCAN-journals PASS "hermes namespace=$jn system=$js (core api unit=$ja)" || rec SCAN-journals FAIL "hermes namespace=$jn system=$js core-api=$ja"
pv=$(grep -c "$CAN" $SY/requests.jsonl); rec SCAN-synthetic-provider INFO "synthetic provider record file: $pv canary hits (records roles/sizes/hashes only)"
nd=$(dumps); cf=$(grep -l '"content_free": true' $HH/sessions/request_dump_* 2>/dev/null | wc -l)
[[ $nd -ge 1 && $nd -eq $cf ]] && rec DUMPS PASS "$nd request dumps written on API errors, all content_free" || rec DUMPS FAIL "dumps=$nd content_free=$cf"
for f in gateway.log agent.log errors.log; do rec LOG-$f INFO "lines=$(wc -l < $HH/logs/$f 2>/dev/null) 'inbound message'=$(grep -c 'inbound message:' $HH/logs/$f 2>/dev/null) 'msg_chars='=$(grep -c 'msg_chars=' $HH/logs/$f 2>/dev/null) canary=$(grep -c "$CAN" $HH/logs/$f 2>/dev/null)"; done
python3 - $HH/logs/lilith-router-decisions.log > $EV/dec.txt <<'PY'
import json, sys
recs = [json.loads(l) for l in open(sys.argv[1], encoding="utf-8")]
print(f"records={len(recs)} with_preview={sum('preview' in r for r in recs)} with_event_id={sum('event_id' in r for r in recs)}")
PY
rec ROUTER-log INFO "$(cat $EV/dec.txt)"
find $HH -xdev -printf '%y %m %u %s %P\n' | LC_ALL=C sort -k5 > $EV/inventory-hermes-home.txt
find $B -maxdepth 2 -printf '%y %m %u %P\n' | LC_ALL=C sort -k4 > $EV/inventory-backups.txt
rec INVENTORY INFO "HERMES_HOME entries=$(wc -l < $EV/inventory-hermes-home.txt); backups entries=$(wc -l < $EV/inventory-backups.txt)"
# SOUL.md: runtime file, F9-B must not change it (recorded here; owner baseline lives in F9-A evidence: 2765a846…)
rec SOUL INFO "$([[ -f $HH/SOUL.md ]] && sha256sum < $HH/SOUL.md | cut -c1-16 || echo absent)"

echo "#### G-9 parity + cleanup"
bash $P/bin/observe_host.sh $EV/g9 >/dev/null
bash $P/bin/compare_observations.sh $PRE/observation $EV/g9 > $EV/g9-cmp.txt && rec G-9-obs PASS "$(tail -1 $EV/g9-cmp.txt)" || rec G-9-obs FAIL "$(grep DIFF $EV/g9-cmp.txt | tr '\n' ' ')"
bash $P/bin/dr5_check.sh $EV/dr5-g9.txt > $EV/dr5-g9-check.txt && rec G-9-DR5 PASS "$(tail -1 $EV/dr5-g9-check.txt | cut -c1-40)" || rec G-9-DR5 FAIL ""
bash $P/bin/rollback.sh remove > $EV/r2.log 2>&1
systemctl daemon-reload; bash $P/bin/observe_host.sh $EV/final >/dev/null
bash $P/bin/compare_observations.sh $EV/M0 $EV/final > $EV/final-cmp.txt && [[ $(ls -A $HH) == memories ]] && rec FINAL CLEAN "M0 == FINAL, HH=memories" || rec FINAL NOT_CLEAN "$(grep DIFF $EV/final-cmp.txt | tr '\n' ' ')"
rec QUARANTINE INFO "rollback quarantine holding the canary (conversation store copies): $(grep -rlaF "$CAN" $B 2>/dev/null | sed "s|$B/||" | paste -sd' ')"
bash /root/f8r4/mirror/synthprov.sh down >/dev/null
[[ $MIRROR_SET_UP == 1 ]] && { bash /root/f8r2/mirror/mirror_teardown.sh > $EV/mirror-teardown.log 2>&1; rec mirror-teardown INFO "$(tail -1 $EV/mirror-teardown.log)"; }
echo; echo "TOTAL: $(grep -cP '\t(PASS|CLEAN|DETECTED|INFO)\t' $RES) ok / $(wc -l < $RES) rows; NOT ok: $(grep -cvP '\t(PASS|CLEAN|DETECTED|INFO)\t' $RES)"
