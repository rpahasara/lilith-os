#!/usr/bin/env bash
# F9-C Track A LOCAL WSL MIRROR rehearsal (refused on lilith-dev-01). Synthetic provider only; no DEV/PROD, no Groq.
#   F8r4 installed + synthetic canary -> U-1 preserve_f8r4 -> U-2 f9c1 install.sh -> U-3 F9-C Core API (mirror stand-in
#   for the governed DEV deployer) + install_f9c.sh + Core API restart -> U-4 token, verify, gateway, canary turn
#   -> D-1 hold-first FORGET drill (blocked-state probes while held) -> D-2 H2/H6/H9/cancel probes + R-0 rollback
#   refusal while pending -> R-2 f9c rollback -> R-3 restore_f8r4 -> parity (protected services, DR-5, observation).
set -uo pipefail
[[ $(hostname) != lilith-dev-01 ]] || { echo "refused on lilith-dev-01"; exit 1; }
W=/root/f9ca; T=$W/tracka; REL9=f293e72-f9c1; REL8=f293e72-f8r4
P9=/var/tmp/f8/hermes-gateway-dev-$REL9; P8=/var/tmp/f8/hermes-gateway-dev-$REL8
HH=/home/lilith/.hermes-dev; B=/var/backups/hermes-gateway-dev; SY=/root/f8r4/synth
CORE=/home/lilith/.hermes/lilith-os-dev; DATA=$CORE/data; LIB=/usr/local/lib/f9ca-mirror; TCORE=/opt/f9ca-mirror/core-api
SIG=/tmp/f9ca-signal; INTENT=/var/lib/hermes-forget/intent/first-interaction.intent; MARK=/var/lib/hermes-forget/in-progress
CAN8=F9CA-CANARY-F8R4; CAN9=F9CA-CANARY-F9C1
RES=$W/rehearsal.tsv; : > $RES; EV=$W/rehearsal-ev; rm -rf $EV; mkdir -p $EV
rec() { printf '%s\t%s\t%s\n' "$1" "$2" "$3" | tee -a "$RES"; }
relay() {  # <message> <session> : the Core API relay (what the Command Center calls); prints the HTTP code
  curl -s -m 170 -o $EV/relay.json -w '%{http_code}' -H 'Content-Type: application/json' \
       -d "{\"message\":\"$1\",\"session\":\"$2\"}" http://127.0.0.1:8765/os/conversation; }
detail() { python3 -c 'import json,sys;d=json.load(open(sys.argv[1]));print(d.get("detail") or d.get("state") or "")' $EV/relay.json 2>/dev/null; }
wait_port() { for _ in $(seq 1 ${2:-90}); do ss -Hltn "sport = :$1" | grep -q . && return 0; sleep 1; done; return 1; }
wait_closed() { for _ in $(seq 1 60); do ss -Hltn "sport = :$1" | grep -q . || return 0; sleep 1; done; return 1; }
gw() { echo "$(systemctl is-active hermes-gateway-dev) cond=$(systemctl show hermes-gateway-dev -p ConditionResult --value)"; }
as_lilith() {  # <unittest selector> : the drill as uid lilith (gets lilith-forget from /etc/group)
  runuser -u lilith -- env -C $LIB HOME=/tmp PYTHONDONTWRITEBYTECODE=1 F9C_CORE_API=$TCORE F9CA_SIGNAL_DIR=$SIG \
    python3 -B -m unittest "$@" 2>&1; }
scan() { grep -rlaF -e "$CAN8" -e "$CAN9" $HH $B /var/lib/hermes-forget /run/hermes-forget 2>/dev/null | sort -u; }
api_restart() { systemctl restart lilith-os-api-dev; for _ in $(seq 1 30); do curl -s -m 2 http://127.0.0.1:8765/health >/dev/null && return 0; sleep 1; done; return 1; }

cleanup() {  # idempotent: also runs when the rehearsal stops early
  trap - EXIT
  echo "#### cleanup (mirror only)"
  for u in hermes-forget.path hermes-forget-hold.path hermes-forget-reconcile.timer; do systemctl stop $u 2>/dev/null; done
  [[ -x /opt/hermes-gateway-dev/current/bin/rollback.sh ]] && bash /opt/hermes-gateway-dev/current/bin/rollback.sh remove > $EV/cleanup-r2.log 2>&1
  rm -f /etc/systemd/system/hermes-forget* /etc/tmpfiles.d/hermes-forget.conf; rm -rf /etc/hermes-forget /etc/systemd/system/hermes-gateway-dev.service.d
  rm -rf /var/lib/hermes-forget /run/hermes-forget $CORE/releases/f9ca-f9c1 $TCORE $LIB $SIG /etc/lilith-os-dev/privacy-authority.key
  [[ -n ${CORE0:-} ]] && ln -sfn "$CORE0" $CORE/current.new && chown -h lilith:lilith $CORE/current.new && mv -Tf $CORE/current.new $CORE/current
  gpasswd -d lilith lilith-forget >/dev/null 2>&1; groupdel lilith-forget 2>/dev/null
  systemctl daemon-reload; api_restart
  bash /root/f8r4/mirror/synthprov.sh down >/dev/null
  [[ ${MIRROR_SET_UP:-0} == 1 ]] && { bash /root/f8r2/mirror/mirror_teardown.sh > $EV/mirror-teardown.log 2>&1; rec mirror-teardown INFO "$(tail -1 $EV/mirror-teardown.log)"; }
  echo; echo "TOTAL: $(grep -cP '	(PASS|INFO)	' $RES) ok / $(wc -l < $RES) rows; NOT ok: $(grep -cvP '	(PASS|INFO)	' $RES)"
}
trap cleanup EXIT

echo "#### S0 mirror baseline"
MIRROR_SET_UP=0
if [[ ! -f /etc/systemd/system/lilith-memory-broker.service ]]; then
  bash /root/f8r2/mirror/mirror_setup.sh /root/f8r2/repo /root/f8hd/build/pkg/uv/uv > $EV/mirror-setup.log 2>&1 \
    && MIRROR_SET_UP=1 && rec mirror-setup PASS "stand-ins up" || { rec mirror-setup FAIL "$(tail -3 $EV/mirror-setup.log)"; exit 1; }
fi
for rb in /var/tmp/f8/*/bin/rollback.sh; do [[ -x $rb ]] && bash $rb remove >/dev/null 2>&1; done
systemctl daemon-reload
[[ -d $B ]] && mkdir -p $W/old && mv $B $W/old/backups-$(date +%s)
[[ -e /var/lib/hermes-forget || -e /etc/hermes-forget ]] && { rec S0 FAIL "F9-C leftovers present"; exit 1; }
CORE0=$(readlink $CORE/current)
python3 -I /root/f8r4/amend/patch_fake_groq.py /root/f8r4/mirror/fake_groq.py >/dev/null
python3 -I /root/f8r4/amend/patch_fake_groq_msgs.py /root/f8r4/mirror/fake_groq.py >/dev/null
bash /root/f8r4/mirror/synthprov.sh up >/dev/null
rm -rf /var/tmp/f8 && install -d -m 0700 /var/tmp/f8
cp /root/f8r4/out/hermes-gateway-dev-$REL8.tar.gz* $W/out/hermes-gateway-dev-$REL9.tar.gz* /var/tmp/f8/
for r in $REL8 $REL9; do
  (cd /var/tmp/f8 && sha256sum -c hermes-gateway-dev-$r.tar.gz.sha256 >/dev/null && tar -xzf hermes-gateway-dev-$r.tar.gz \
    && cd hermes-gateway-dev-$r && sha256sum --quiet -c MANIFEST.sha256) && rec G-2-$r PASS "$(cut -c1-16 /var/tmp/f8/hermes-gateway-dev-$r.tar.gz.sha256) + MANIFEST" \
    || { rec G-2-$r FAIL ""; exit 1; }
done
systemctl start lilith-memory-broker.service lilith-authority-dev.service lilith-recovery-witness.service lilith-os-api-dev.service; sleep 4
bash $P9/bin/observe_host.sh $EV/M0 >/dev/null
bash $P9/bin/dr5_check.sh $EV/dr5-M0.txt > $EV/dr5-M0-check.txt && rec M0-DR5 PASS "$(tail -1 $EV/dr5-M0-check.txt | cut -c1-48)" || { rec M0-DR5 FAIL ""; exit 1; }
REQ0=$(wc -l < $SY/requests.jsonl)

echo "#### F8r4 (accepted Phase B) installed with state"
bash $P8/bin/backup_pre_install.sh >/dev/null
F8_SIM=1 bash $P8/bin/install.sh > $EV/f8r4-install.log 2>&1 && grep -q "F8_INSTALL_STAGED $REL8" $EV/f8r4-install.log \
  && rec F8R4-install PASS staged || { rec F8R4-install FAIL "$(tail -2 $EV/f8r4-install.log)"; exit 1; }
bash $P8/bin/provision_console_token.sh >/dev/null
printf '%s\n' "$(cat $SY/synthetic-key)" | script -qec "bash $P8/bin/provision_provider_key.sh" /dev/null > $EV/f8r4-key.log 2>&1
R8=/opt/hermes-gateway-dev/current
$R8/venv/bin/python -I -B $R8/bin/verify_release.py --full > $EV/f8r4-verify.log 2>&1 && rec F8R4-verify PASS "$(tail -1 $EV/f8r4-verify.log)" || rec F8R4-verify FAIL "$(tail -2 $EV/f8r4-verify.log)"
bash $R8/bin/gate_budget.sh reset --owner-approved mirror-only-f9ca >/dev/null 2>&1
systemctl start hermes-gateway-dev; wait_port 9901 120 && wait_port 9911 60 || { rec F8R4-start FAIL ""; exit 1; }
sleep 3
c=$(relay "$CAN8 synthetic F8r4 turn: reply with one short sentence." f9ca-f8r4); rec F8R4-turn INFO "relay http=$c [$(detail)]"
F8R4_SHA=$(sha256sum < $R8/RELEASE.sha256 | cut -c1-64); KEY8=$(sha256sum < /etc/hermes-provider-gate-dev/credentials/groq-api-key | cut -c1-16)
bash $P8/bin/observe_host.sh $EV/F8R4 >/dev/null
rec F8R4-state INFO "release_sha=${F8R4_SHA:0:16} key=$KEY8 canary-files=$(scan | wc -l) provider-requests=$(( $(wc -l < $SY/requests.jsonl) - REQ0 ))"
REQ8=$(wc -l < $SY/requests.jsonl)

echo "#### U-1 preserve F8r4"
F8_SIM=1 F8R4_RELEASE_SHA=$F8R4_SHA bash $P9/bin/preserve_f8r4.sh > $EV/u1.log 2>&1 && grep -q F8R4_PRESERVED $EV/u1.log \
  && rec U-1 PASS "$(tail -1 $EV/u1.log | cut -c1-200)" || { rec U-1 FAIL "$(tail -3 $EV/u1.log | tr '\n' ' ')"; exit 1; }
PRES=$(grep -o 'F8R4_PRESERVED [^ ]*' $EV/u1.log | cut -d' ' -f2)
[[ $(ls -A $HH) == memories && ! -e /etc/hermes-provider-gate-dev ]] && rec U-1-clean PASS "HERMES_HOME=memories; gate config+key quarantined" || rec U-1-clean FAIL "$(ls -A $HH | tr '\n' ' ')"

echo "#### U-2 f9c1 install"
bash $P9/bin/backup_pre_install.sh > $EV/u2-backup.log; PRE9=$(ls -d $B/pre-* | tail -1)
F8_SIM=1 bash $P9/bin/install.sh > $EV/u2-install.log 2>&1 && grep -q "F8_INSTALL_STAGED $REL9" $EV/u2-install.log \
  && rec U-2 PASS "staged $REL9" || { rec U-2 FAIL "$(tail -2 $EV/u2-install.log)"; exit 1; }

echo "#### U-3 F9-C Core API (mirror stand-in for the governed DEV deployer) + install_f9c + Core API restart"
NEWREL=$CORE/releases/f9ca-f9c1
rm -rf $NEWREL; mkdir -p $NEWREL/lilith_memory
cp $W/repo/services/core-api/app.py $W/repo/services/core-api/requirements.txt $NEWREL/
cp $W/repo/services/core-api/lilith_memory/*.py $NEWREL/lilith_memory/
chown -R lilith:lilith $NEWREL; ln -sfn $NEWREL $CORE/current.new && chown -h lilith:lilith $CORE/current.new && mv -Tf $CORE/current.new $CORE/current
rm -rf $TCORE; mkdir -p $(dirname $TCORE); cp -a $W/repo/services/core-api $TCORE; chmod -R a+rX /opt/f9ca-mirror
mkdir -p $LIB && cp $T/mirror/test_f9ca_drill.py $LIB/ && chmod -R a+rX $LIB
(cd $TCORE/tests && python3 -I -c "import sys; sys.path.insert(0,'.'); from test_privacy_hermes_owner_v2 import SECRET; sys.stdout.buffer.write(SECRET)") > /etc/lilith-os-dev/privacy-authority.key
chown root:lilith /etc/lilith-os-dev/privacy-authority.key; chmod 0640 /etc/lilith-os-dev/privacy-authority.key
[[ -f $DATA/privacy_governance.dev.db ]] || { runuser -u lilith -- python3 -c "import sqlite3; c=sqlite3.connect('$DATA/privacy_governance.dev.db'); c.execute('CREATE TABLE placeholder(x)'); c.commit()"; chmod 0600 $DATA/privacy_governance.dev.db; }
F8_SIM=1 F9C_CORE_API_DIR=$CORE/current/lilith_memory F9C_PRIVACY_SECRET=/etc/lilith-os-dev/privacy-authority.key \
  bash $P9/bin/install_f9c.sh > $EV/u3-install-f9c.log 2>&1 && grep -q F9C_INSTALLED $EV/u3-install-f9c.log \
  && rec U-3-install_f9c PASS "$(tail -1 $EV/u3-install-f9c.log | cut -c1-120)" || { rec U-3-install_f9c FAIL "$(tail -3 $EV/u3-install-f9c.log | tr '\n' ' ')"; exit 1; }
cmp -s /etc/hermes-forget/coreapi/lilith_memory/privacy_governance.py $CORE/current/lilith_memory/privacy_governance.py \
  && [[ $(stat -c %U:%a /etc/hermes-forget/coreapi/lilith_memory/privacy_governance.py) == root:644 ]] \
  && rec U-3-coreapi-copy PASS "executor imports a root-owned copy equal to the lilith-owned deployed release" || rec U-3-coreapi-copy FAIL ""
c=$(relay "probe before Core API restart" f9ca-probe); rec U-3-before-restart INFO "relay http=$c [$(detail)] (Core API not yet in lilith-forget)"
api_restart || rec U-3-api FAIL "Core API not healthy"
G=$(getent group lilith-forget | cut -d: -f3)
grep -qw "$G" <(grep ^Groups: /proc/$(systemctl show lilith-os-api-dev -p MainPID --value)/status) \
  && rec U-3-api-group PASS "Core API process carries lilith-forget ($G) after restart" || rec U-3-api-group FAIL ""
for u in hermes-forget.path hermes-forget-hold.path hermes-forget-reconcile.timer; do rec U-3-$u INFO "$(systemctl is-active $u) $(systemctl is-enabled $u)"; done
bash $P9/bin/dr5_check.sh $EV/dr5-u3.txt > $EV/dr5-u3-check.txt && rec U-3-DR5 PASS "$(tail -1 $EV/dr5-u3-check.txt | cut -c1-48)" || rec U-3-DR5 FAIL ""

echo "#### U-4 token, verify, gateway (no provider key: no provider call is possible), canary"
bash $P9/bin/provision_console_token.sh >/dev/null
R9=/opt/hermes-gateway-dev/current
$R9/venv/bin/python -I -B $R9/bin/verify_release.py --full > $EV/u4-verify.log 2>&1; rec U-4-verify INFO "rc=$? $(tail -1 $EV/u4-verify.log | cut -c1-140)"
rec U-4-env INFO ".env keys: $(cut -d= -f1 $HH/.env | sort | paste -sd,)"
systemctl start hermes-gateway-dev; wait_port 9901 120 && rec U-4-start PASS "gateway listening" || { rec U-4-start FAIL "$(gw)"; exit 1; }
sleep 3
c=$(relay "$CAN9 synthetic F9 turn one." f9ca-f9-a); rec U-4-turn1 INFO "relay http=$c [$(detail)]"
c=$(relay "$CAN9 synthetic F9 turn two." f9ca-f9-a); rec U-4-turn2 INFO "relay http=$c [$(detail)]"
[[ $(wc -l < $SY/requests.jsonl) -eq $REQ8 ]] && rec U-4-no-provider PASS "0 provider requests since the F8r4 phase" || rec U-4-no-provider FAIL "$(( $(wc -l < $SY/requests.jsonl) - REQ8 )) requests"
rec U-4-canary INFO "canary files before FORGET: $(scan | sed "s|$B/||" | paste -sd' ')"

echo "#### D-1 hold-first FORGET drill"
rm -rf $SIG; mkdir -p $SIG; chown lilith $SIG
as_lilith test_f9ca_drill.Drill.test_hold_first_forget_through_the_installed_units > $EV/d1.log &
CP=$!
for _ in $(seq 1 240); do [[ -e $SIG/held ]] && break; sleep 0.5; done
if [[ -e $SIG/held ]]; then
  st=$(stat -c '%U:%G %a' $INTENT 2>/dev/null)
  ph=$(python3 -c "import sqlite3,sys; c=sqlite3.connect('file:'+sys.argv[1]+'?mode=ro', uri=True); print(c.execute('SELECT COUNT(*) FROM privacy_hold').fetchone()[0])" "$DATA/privacy_governance.dev.db" 2>&1)
  c=$(relay "TEST_ONLY turn while held" f9ca-f9-a); d=$(detail)
  systemctl start hermes-gateway-dev 2>/dev/null; sleep 1; g=$(gw)
  runuser -u lilith -- rm -f $INTENT 2>/dev/null; still=$([[ -e $INTENT ]] && echo kept || echo REMOVED)
  ss -Hltn 'sport = :9901' | grep -q . && port=open || port=closed
  rec D-1-held INFO "intent=[$st] privacy_holds=$ph relay=$c/$d gateway-start=[$g] port=$port lilith-rm=$still"
  [[ $st == "root:lilith-forget 640" && $ph == 0 && $c == 503 && $d == FORGET_HOLD_ACTIVE && $g =~ ^(inactive|failed)\ cond=no$ && $port == closed && $still == kept ]] \
    && rec D-1-blocked PASS "held before Privacy acts: relay 503, gateway start refused, port closed, Core API cannot remove the intent" \
    || rec D-1-blocked FAIL "see D-1-held"
else rec D-1-held FAIL "hold never established: $(tail -5 $EV/d1.log | tr '\n' ' ')"; fi
touch $SIG/continue; wait $CP
grep -q 'MIRROR_RESULT status=COMPLETE' $EV/d1.log && rec D-1 PASS "$(grep MIRROR_RESULT $EV/d1.log)" || rec D-1 FAIL "$(tail -8 $EV/d1.log | tr '\n' ' ' | cut -c1-400)"
for _ in $(seq 1 120); do [[ ! -e $INTENT && ! -e $MARK ]] && ss -Hltn 'sport = :9901' | grep -q . && break; sleep 1; done
[[ ! -e $INTENT && ! -e $MARK ]] && wait_port 9901 5 && rec D-1-release PASS "root released intent + marker after Privacy completion; gateway restarted" \
  || rec D-1-release FAIL "intent=$([[ -e $INTENT ]] && echo present) marker=$([[ -e $MARK ]] && echo present) $(gw)"
rec D-1-journal INFO "executor: $(journalctl -u hermes-forget-executor -o cat --no-pager | grep -o '"event": "[A-Z_]*"' | sort | uniq -c | tr -s ' ' | paste -sd' '); hold: $(journalctl -u hermes-forget-hold -o cat --no-pager | grep -o '"event": "[A-Z_]*"' | sort | uniq -c | tr -s ' ' | paste -sd' ')"
N=$(scan); [[ -z $N ]] && rec D-1-scan PASS "F8r4 + F9 canaries: 0 files in HERMES_HOME, backups (incl. the F8r4 quarantine), executor state" || rec D-1-scan FAIL "$(echo $N | sed "s|$B/||g")"
jn=$(journalctl --namespace=hermes-gateway-dev -o cat --no-pager | grep -c -e "$CAN8" -e "$CAN9")
rec D-1-ns-journal INFO "hermes namespace journal canary hits=$jn"
c=$(relay "TEST_ONLY after FORGET" f9ca-f9-b); rec D-1-after INFO "relay after release http=$c [$(detail)]"
rec D-1-receipt INFO "$(ls /var/lib/hermes-forget/receipts | wc -l) receipt(s); epochs=$(wc -l < /var/lib/hermes-forget/epochs/epochs.log)"

echo "#### D-2 H2 / H9 / H6-stall / cancel on real systemd + R-0 rollback refusal"
as_lilith test_f9ca_drill.Drill.test_prepare_an_unforgotten_privacy_database > $EV/d2-prep.log
grep -q MIRROR_PREPARED $EV/d2-prep.log || rec D-2-prep FAIL "$(tail -3 $EV/d2-prep.log | tr '\n' ' ')"
systemctl stop hermes-forget-hold.path
as_lilith test_f9ca_drill.RecordIntent > $EV/d2-intent.log; grep -q MIRROR_INTENT $EV/d2-intent.log || rec D-2-intent FAIL "$(tail -3 $EV/d2-intent.log)"
c=$(relay "TEST_ONLY turn with the intent recorded, gateway still running" f9ca-f9-b); d=$(detail); g1=$(systemctl is-active hermes-gateway-dev)
[[ $c == 503 && $d == FORGET_HOLD_ACTIVE && $g1 == active ]] && rec H2-relay PASS "intent only (hold not run, gateway still up): relay refuses at once (503 FORGET_HOLD_ACTIVE)" || rec H2-relay FAIL "http=$c $d gateway=$g1"
systemctl restart hermes-gateway-dev 2>/dev/null; sleep 1; g=$(gw)
[[ $g =~ ^(inactive|failed)\ cond=no$ ]] && rec H2-restart PASS "a gateway restart cannot resume while the intent exists ($g)" || rec H2-restart FAIL "$g"
systemctl start hermes-forget-hold.path; for _ in $(seq 1 30); do [[ $(stat -c %U $INTENT) == root ]] && break; sleep 1; done
runuser -u lilith -- rm -f $INTENT 2>/dev/null
[[ -e $INTENT && $(stat -c %U $INTENT) == root ]] && rec H9 PASS "after the root hold the Core API identity cannot remove the intent" || rec H9 FAIL "$(stat -c '%U %a' $INTENT 2>&1)"
systemctl start hermes-forget-reconcile.service; sleep 2
[[ -e $INTENT ]] && rec H6-stall PASS "no Privacy authorization, FORGET not complete: reconcile keeps the intent (durable, blocking)" || rec H6-stall FAIL "released"
bash $R9/bin/rollback.sh remove > $EV/r0.log 2>&1; r0=$?
grep -q F9C_ROLLBACK_REFUSED_FORGET_PENDING $EV/r0.log && [[ $r0 -ne 0 && -e /etc/hermes-forget/executor.json \
   && $(systemctl is-active hermes-forget-hold.path) == active && $(systemctl show cron -p NeedDaemonReload --value) == no ]] \
  && rec R-0 PASS "rollback remove refused while a FORGET intent is pending, before changing anything (units active, nothing pending)" \
  || rec R-0 FAIL "rc=$r0 hold.path=$(systemctl is-active hermes-forget-hold.path) $(tail -2 $EV/r0.log | tr '\n' ' ')"
X="$R9/python/cpython-3.11.16-linux-x86_64-gnu/bin/python3.11 -I -B $R9/bin/hermes_forget_executor.py"
$X --cancel-intent > $EV/cancel1.log 2>&1; c1=$?
$X --cancel-intent --confirm-owner-approved > $EV/cancel2.log 2>&1; c2=$?
[[ $c1 -eq 2 && $c2 -eq 0 && ! -e $INTENT ]] && rec cancel PASS "unconfirmed cancel refused; owner-approved cancel removed the never-authorized intent" || rec cancel FAIL "c1=$c1 c2=$c2"
systemctl start hermes-forget-restart.service; wait_port 9901 120 && rec cancel-resume PASS "gateway resumes only after the intent is gone" || rec cancel-resume FAIL "$(gw)"

echo "#### R-2 f9c rollback, R-3 restore F8r4"
bash $P9/bin/observe_host.sh $EV/F9 >/dev/null
bash $R9/bin/rollback.sh remove > $EV/r2.log 2>&1 && grep -q F8_ROLLBACK_REMOVED $EV/r2.log && rec R-2 PASS "$(tail -1 $EV/r2.log | cut -c1-120)" || rec R-2 FAIL "$(tail -3 $EV/r2.log | tr '\n' ' ')"
[[ -f /var/lib/hermes-forget/epochs/epochs.log && ! -e /etc/hermes-forget ]] && rec R-2-epochs PASS "erasure epochs kept for the restore guard; F9-C config quarantined" || rec R-2-epochs FAIL ""
F8_SIM=1 bash $P9/bin/restore_f8r4.sh "$PRES" > $EV/r3.log 2>&1 && grep -q F8R4_RESTORED $EV/r3.log \
  && rec R-3 PASS "$(grep -E '^inventory:|F8R4_RESTORED' $EV/r3.log | paste -sd' ' | cut -c1-260)" || rec R-3 FAIL "$(tail -4 $EV/r3.log | tr '\n' ' ' | cut -c1-400)"
[[ $(sha256sum < /etc/hermes-provider-gate-dev/credentials/groq-api-key | cut -c1-16) == "$KEY8" ]] && rec R-3-key PASS "F8r4 provider key restored byte-identical" || rec R-3-key FAIL ""
N=$(scan); [[ -z $N ]] && rec R-3-scan PASS "restored F8r4 carries no pre-FORGET conversation (empty store)" || rec R-3-scan FAIL "$(echo $N | sed "s|$B/||g")"
sleep 3; c=$(relay "TEST_ONLY F8r4 after restore" f9ca-f8r4-after); rec R-3-turn INFO "restored F8r4 relay http=$c [$(detail)]"
bash $P9/bin/dr5_check.sh $EV/dr5-final.txt > $EV/dr5-final-check.txt && rec FINAL-DR5 PASS "$(tail -1 $EV/dr5-final-check.txt | cut -c1-48)" || rec FINAL-DR5 FAIL ""
bash $P9/bin/observe_host.sh $EV/R3 >/dev/null
bash $P9/bin/compare_observations.sh $EV/F8R4 $EV/R3 > $EV/f8r4-vs-r3.txt; rec OBS-F8R4-vs-restored INFO "$(grep -c DIFF $EV/f8r4-vs-r3.txt) diff lines: $(grep DIFF $EV/f8r4-vs-r3.txt | cut -c1-100 | paste -sd'|' | cut -c1-500)"
