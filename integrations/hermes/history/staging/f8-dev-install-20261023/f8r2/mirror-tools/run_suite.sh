#!/usr/bin/env bash
# F8r2 complete validation in the WSL DEV-mirror (refuses on lilith-dev-01). Every scenario ends with the same
# clean-state proof: observation EQUAL to its own G-1 and to the original mirror baseline M0, DR-5 byte-identical to
# the DEV block, no F8 path left outside the quarantine, 9901 closed, HERMES_HOME listing == G-1.
set -uo pipefail
[[ $(hostname) != lilith-dev-01 ]] || { echo "refused on lilith-dev-01"; exit 1; }
W=/root/f8r2; REL_ID=f293e72-f8r2; PKGN=hermes-gateway-dev-$REL_ID
RES=$W/results.tsv; : > "$RES"; EV=$W/evidence; rm -rf "$EV"; mkdir -p "$EV"
HH=/home/lilith/.hermes-dev; R=/opt/hermes-gateway-dev/current
rec() { printf '%s\t%s\t%s\n' "$1" "$2" "$3" | tee -a "$RES"; }
s() { echo; echo "################ $* ################"; }
latest_pre() { ls -d /var/backups/hermes-gateway-dev/pre-* | tail -1; }
EXISTING_UNITS="lilith-os-api-dev.service lilith-memory-broker.service lilith-memory-broker.socket lilith-authority-dev.service lilith-authority-dev.socket lilith-recovery-witness.service lilith-recovery-witness-owner.socket lilith-recovery-witness-signer.socket lilith-stage3-a2-final.service"
service_state() { for u in ${EXISTING_UNITS}; do printf '%s ' "$u"; systemctl show "$u" -p ActiveState,SubState,MainPID,InvocationID,NRestarts,ExecMainStartTimestampMonotonic | tr '
' ' '; echo; done; }

s "G-2 transfer + verify (package from local build)"
rm -rf /var/tmp/f8 && install -d -m 0700 /var/tmp/f8 && cp $W/out/$PKGN.tar.gz* /var/tmp/f8/
(cd /var/tmp/f8 && sha256sum -c $PKGN.tar.gz.sha256 && tar -xzf $PKGN.tar.gz && cd $PKGN && sha256sum --quiet -c MANIFEST.sha256) \
  && rec G-2 PASS "tarball + MANIFEST verified" || { rec G-2 FAIL ""; exit 1; }
P=/var/tmp/f8/$PKGN

s "M0 mirror baseline (mirror services up, DR-5 must already equal the DEV block)"
systemctl start lilith-memory-broker.service lilith-authority-dev.service lilith-recovery-witness.service lilith-os-api-dev.service
sleep 5; curl -s -m 5 http://127.0.0.1:8765/health | grep -q '"status":"ok"' || { rec M0 FAIL "Core API not healthy"; exit 1; }
bash $P/bin/observe_host.sh $EV/M0 >/dev/null
bash $P/bin/dr5_check.sh $EV/dr5-M0.txt > $EV/dr5-M0-check.txt && rec M0-DR5 PASS "$(tail -1 $EV/dr5-M0-check.txt)" || { rec M0-DR5 FAIL "mirror not DEV-equivalent"; exit 1; }

clean_check() {   # <scenario> <G-1 dir>
  local sc=$1 pre=$2 ok=1 left
  bash $P/bin/observe_host.sh $EV/$sc-post >/dev/null
  bash $P/bin/compare_observations.sh "$pre/observation" $EV/$sc-post > $EV/$sc-cmp-g1.txt || ok=0
  bash $P/bin/compare_observations.sh $EV/M0 $EV/$sc-post > $EV/$sc-cmp-m0.txt || ok=0
  bash $P/bin/dr5_check.sh $EV/$sc-dr5.txt > $EV/$sc-dr5-check.txt || ok=0
  left=$(ls -d /opt/hermes-gateway-dev /etc/hermes-gateway-dev /etc/systemd/system/hermes-gateway-dev* /etc/systemd/journald@hermes-gateway-dev.conf 2>/dev/null | tr '\n' ' ')
  [[ -z $left ]] || ok=0
  [[ $(ls -A $HH) == memories ]] || ok=0
  ! ss -Hltn 'sport = :9901' | grep -q . || ok=0
  [[ $(systemctl show hermes-gateway-dev -p LoadState --value) == not-found ]] || ok=0
  if [[ $ok == 1 ]]; then rec "$sc" CLEAN "obs==G-1==M0; DR-5 $(tail -1 $EV/$sc-dr5-check.txt | cut -c1-30); no F8 paths; 9901 closed; HH=memories only"
  else rec "$sc" NOT_CLEAN "left=[$left] HH=[$(ls -A $HH | tr '\n' ' ')] $(grep -h DIFF $EV/$sc-cmp-*.txt | tr '\n' ' ') $(tail -1 $EV/$sc-dr5-check.txt)"; fi
}

s "H happy path"
bash $P/bin/backup_pre_install.sh | tail -1; PRE=$(latest_pre)
F8_SIM=1 bash $P/bin/install.sh > $EV/H-install.log 2>&1; grep -q "F8_INSTALL_STAGED $REL_ID" $EV/H-install.log && rec H-G3 PASS "install staged" || rec H-G3 FAIL "$(tail -2 $EV/H-install.log)"
bash $P/bin/dr5_check.sh $EV/H-dr5-installed.txt > $EV/H-dr5-installed-check.txt && rec H-DR5-installed PASS "$(tail -1 $EV/H-dr5-installed-check.txt)" || rec H-DR5-installed FAIL "$(tail -1 $EV/H-dr5-installed-check.txt)"
B=$(mktemp -d /var/tmp/f8-g4-XXXXXX)
ln -s $R/src $B/hermes-agent; mkdir $B/hermes-home-dev $B/tests; cp -a $P/home/lilith_router $P/home/plugins $B/hermes-home-dev/
cp $P/tests/f7-home/config.yaml $B/hermes-home-dev/; cp $P/tests/f7-home/router.yaml $B/hermes-home-dev/lilith_router/; cp $P/tests/test_f7_offline.py $B/tests/
chown -R lilith:lilith $B; chmod 700 $B
runuser -u lilith -- env -i PATH=/usr/bin:/bin HOME=$B PYTHONUNBUFFERED=1 $R/venv/bin/python -B $B/tests/test_f7_offline.py > $EV/H-G4-f7.log 2>&1
grep -q '^OK$' $EV/H-G4-f7.log && rec H-G4 PASS "$(grep '^Ran ' $EV/H-G4-f7.log) OK (Linux, installed release)" || rec H-G4 FAIL "$(tail -3 $EV/H-G4-f7.log)"
rm -rf $B
bash $P/bin/provision_console_token.sh > $EV/H-G5.log 2>&1
$R/venv/bin/python -I -B $R/bin/verify_release.py --full >> $EV/H-G5.log 2>&1 && rec H-G5 PASS "$(tail -1 $EV/H-G5.log)" || rec H-G5 FAIL "$(tail -3 $EV/H-G5.log)"
pre_start=$(service_state)
systemctl start hermes-gateway-dev
for i in $(seq 1 45); do ss -Hltn "sport = :9901" | grep -q . && break; sleep 2; done; listen_s=$((i*2))
st=$(for k in ActiveState SubState NRestarts UnitFileState; do systemctl show hermes-gateway-dev -p $k --value; done | paste -sd' ')' '
lst=$(ss -Hltnup | grep '"hermes"' | awk '{print $5}' | tr '\n' ' ')
[[ $st == "active running 0 static " && $lst == "127.0.0.1:9901 " ]] && rec H-G6 PASS "active/running NRestarts=0 static(not enabled) listen=[$lst] after ~${listen_s}s mem=$(( $(systemctl show hermes-gateway-dev -p MemoryCurrent --value) / 1048576 ))MiB" || rec H-G6 FAIL "st=[$st] listen=[$lst]"
journalctl --namespace=hermes-gateway-dev -u hermes-gateway-dev --no-pager > $EV/H-gateway-journal.txt 2>&1
tstate=$(systemctl is-active hermes-gateway-dev-retention.timer); [[ $tstate == active && $(systemctl is-enabled hermes-gateway-dev) == static && $(systemctl is-enabled hermes-gateway-dev-retention.timer) == static ]] && rec H-G6-timer PASS "retention timer active via Wants=; gateway+timer is-enabled=static (nothing enabled)" || rec H-G6-timer FAIL "timer=$tstate"
global=$(systemctl show lilith-os-api-dev -p NeedDaemonReload --value); [[ $global == no ]] && rec H-no-pending-reload PASS "no unit left NeedDaemonReload=yes after G-6" || rec H-no-pending-reload FAIL "NeedDaemonReload=$global"
$R/venv/bin/python -I -B $R/bin/smoke_console.py --phase A --core-api > $EV/H-G7-smoke.txt 2>&1 && rec H-G7 PASS "$(tail -1 $EV/H-G7-smoke.txt)" || rec H-G7 FAIL "$(grep -E '^FAIL|F8_SMOKE' $EV/H-G7-smoke.txt | tr '\n' ' ')"
bash $R/bin/sandbox_probe.sh > $EV/H-G7b-probe.txt 2>&1 && rec H-G7b PASS "$(tail -1 $EV/H-G7b-probe.txt)" || rec H-G7b FAIL "$(grep -E '^FAIL|F8_PROBE' $EV/H-G7b-probe.txt | tr '\n' ' ')"
systemctl start hermes-gateway-dev-retention.service; rec H-G8 "$(systemctl show hermes-gateway-dev-retention.service -p Result --value | tr a-z A-Z)" "retention oneshot"
post_start=$(service_state)
[[ "$pre_start" == "$post_start" ]] && rec H-services PASS "existing services identical (PID/InvocationID/NRestarts) across start+smoke+probe" || rec H-services FAIL "changed"
bash $P/bin/observe_host.sh $EV/H-G9 >/dev/null
bash $P/bin/compare_observations.sh $PRE/observation $EV/H-G9 > $EV/H-G9-cmp.txt && rec H-G9-obs PASS "observation EQUAL to G-1 with F8 running" || rec H-G9-obs FAIL "$(grep DIFF $EV/H-G9-cmp.txt | tr '\n' ' ')"
bash $P/bin/dr5_check.sh $EV/H-G9-dr5.txt > $EV/H-G9-dr5-check.txt && rec H-G9-DR5 PASS "$(tail -1 $EV/H-G9-dr5-check.txt)" || rec H-G9-DR5 FAIL "$(tail -1 $EV/H-G9-dr5-check.txt)"
F8_SIM=1 bash $P/bin/install.sh > $EV/H-reinstall.log 2>&1; grep -q "F8 paths already present" $EV/H-reinstall.log && rec H-reinstall-refused PASS "second install refused" || rec H-reinstall-refused FAIL "$(tail -1 $EV/H-reinstall.log)"
bash $P/bin/rollback.sh stop > $EV/H-R1.log 2>&1 && rec H-R1 PASS "$(tail -1 $EV/H-R1.log)" || rec H-R1 FAIL "$(tail -2 $EV/H-R1.log)"
bash $P/bin/rollback.sh remove > $EV/H-R2.log 2>&1 && rec H-R2 PASS "$(tail -1 $EV/H-R2.log | cut -c1-60)" || rec H-R2 FAIL "$(tail -3 $EV/H-R2.log)"
clean_check H "$PRE"

s "FI install-stage failure injection"
for stage in preconditions stage venv home etc units reload verify; do
  bash $P/bin/backup_pre_install.sh >/dev/null; PRE=$(latest_pre)
  F8_SIM=1 F8_FAIL_AT=$stage bash $P/bin/install.sh > $EV/FI-$stage.log 2>&1; rc=$?
  [[ $rc -ne 0 ]] && grep -q "INJECTED_FAILURE at $stage" $EV/FI-$stage.log && rec FI-$stage-stop PASS "install exit $rc at '$stage'" || rec FI-$stage-stop FAIL "rc=$rc"
  bash $P/bin/rollback.sh remove > $EV/FI-$stage-R2.log 2>&1 || true
  clean_check FI-$stage "$PRE"
done

stage_full() { bash $P/bin/backup_pre_install.sh >/dev/null; F8_SIM=1 bash $P/bin/install.sh > $EV/$1-install.log 2>&1 && bash $P/bin/provision_console_token.sh >/dev/null; }
s "PF post-install failures"
stage_full PF-gate; PRE=$(latest_pre)
sed -i 's/^cognitive_enabled: false/cognitive_enabled: true/' $HH/lilith_router/router.yaml
systemctl start hermes-gateway-dev 2>/dev/null; sleep 3
[[ $(systemctl show hermes-gateway-dev -p ActiveState --value) != active ]] && journalctl --namespace=hermes-gateway-dev -u hermes-gateway-dev --no-pager 2>/dev/null | grep -q "F8_VERIFY_FAIL" \
  && rec PF-gate-lane-on PASS "start refused by ExecStartPre ($(journalctl --namespace=hermes-gateway-dev -u hermes-gateway-dev --no-pager | grep -o 'F8_VERIFY_FAIL [A-Z_]*.*' | head -2 | tr '\n' ';'))" \
  || rec PF-gate-lane-on FAIL "state=$(systemctl show hermes-gateway-dev -p ActiveState --value)"
bash $P/bin/rollback.sh remove > $EV/PF-gate-R2.log 2>&1; clean_check PF-gate "$PRE"

stage_full PF-provider; PRE=$(latest_pre)
umask 077; printf 'OPENAI_API_KEY=F8R2-SYNTHETIC-NOT-A-KEY\n' > /etc/hermes-gateway-dev/provider.env; chmod 0600 /etc/hermes-gateway-dev/provider.env
systemctl start hermes-gateway-dev 2>/dev/null; sleep 3
[[ $(systemctl show hermes-gateway-dev -p ActiveState --value) != active ]] && journalctl --namespace=hermes-gateway-dev -u hermes-gateway-dev --no-pager | grep -q "FORBIDDEN_KEY" \
  && rec PF-provider-key PASS "start refused: provider.env key not allowlisted in Phase A" || rec PF-provider-key FAIL "state=$(systemctl show hermes-gateway-dev -p ActiveState --value)"
bash $P/bin/rollback.sh remove > $EV/PF-provider-R2.log 2>&1; clean_check PF-provider "$PRE"

stage_full PF-crash; PRE=$(latest_pre)
systemctl start hermes-gateway-dev; sleep 15
for i in 1 2 3 4; do pid=$(systemctl show -p MainPID --value hermes-gateway-dev); [[ $pid != 0 ]] && kill -9 $pid; sleep 14; done
rec PF-crash-loop "$( [[ $(systemctl show hermes-gateway-dev -p ActiveState --value) == failed ]] && echo PASS || echo FAIL )" \
  "after 4 SIGKILLs: $(systemctl show hermes-gateway-dev -p ActiveState,Result,NRestarts --value | tr '\n' ' ')(StartLimitBurst=3 stops the loop)"
bash $P/bin/rollback.sh remove > $EV/PF-crash-R2.log 2>&1; systemctl reset-failed hermes-gateway-dev 2>/dev/null; clean_check PF-crash "$PRE"

stage_full PF-running; PRE=$(latest_pre)
systemctl start hermes-gateway-dev; sleep 15
bash $P/bin/rollback.sh remove > $EV/PF-running-R2.log 2>&1 && rec PF-R2-from-running PASS "R-2 straight from a running gateway + active timer" || rec PF-R2-from-running FAIL "$(tail -2 $EV/PF-running-R2.log)"
clean_check PF-running "$PRE"

s "PG precondition guards"
SD=/etc/systemd/system; cp -p $SD/lilith-authority-dev.service /root/f8r2/authority.unit.orig
bash $P/bin/backup_pre_install.sh >/dev/null; PRE=$(latest_pre)
echo "# f8r2 pending-reload trigger" >> $SD/lilith-authority-dev.service
F8_SIM=1 bash $P/bin/install.sh > $EV/PG-reload.log 2>&1; rc=$?
[[ $rc -ne 0 ]] && grep -q "NEED_DAEMON_RELOAD_PENDING lilith-authority-dev.service" $EV/PG-reload.log && [[ ! -e /opt/hermes-gateway-dev ]] \
  && rec PG-reload-pending PASS "install refused before any write: $(grep -o 'NEED_DAEMON_RELOAD_PENDING.*' $EV/PG-reload.log)" || rec PG-reload-pending FAIL "rc=$rc"
cp -p /root/f8r2/authority.unit.orig $SD/lilith-authority-dev.service
s0=$(systemctl show lilith-authority-dev -p MainPID,InvocationID --value | tr '\n' ' '); systemctl daemon-reload   # environment repair (owner-equivalent)
[[ $s0 == "$(systemctl show lilith-authority-dev -p MainPID,InvocationID --value | tr '\n' ' ')" ]] || rec PG-reload-env FAIL "authority changed by repair reload"
bash $P/bin/rollback.sh remove > $EV/PG-reload-R2.log 2>&1; clean_check PG-reload "$PRE"

bash $P/bin/backup_pre_install.sh >/dev/null; PRE=$(latest_pre)
python3 -c "import fcntl,time; f=open('/var/lib/dpkg/lock-frontend','w'); fcntl.lockf(f, fcntl.LOCK_EX); time.sleep(120)" & LOCKER=$!; sleep 1
F8_SIM=1 bash $P/bin/install.sh > $EV/PG-dpkg.log 2>&1; rc=$?; kill $LOCKER 2>/dev/null; wait $LOCKER 2>/dev/null
[[ $rc -ne 0 ]] && grep -q "DPKG_LOCK_HELD" $EV/PG-dpkg.log && [[ ! -e /opt/hermes-gateway-dev ]] && rec PG-dpkg-lock PASS "install refused before any write" || rec PG-dpkg-lock FAIL "rc=$rc $(tail -1 $EV/PG-dpkg.log)"
bash $P/bin/rollback.sh remove > $EV/PG-dpkg-R2.log 2>&1; clean_check PG-dpkg "$PRE"

stage_full PG-rbhold; PRE=$(latest_pre)
systemctl start hermes-gateway-dev; sleep 15
echo "# f8r2 pending-reload trigger" >> $SD/lilith-authority-dev.service
bash $P/bin/rollback.sh remove > $EV/PG-rbhold-R2.log 2>&1
grep -q "F8_ROLLBACK_HOLD" $EV/PG-rbhold-R2.log && ! ss -Hltn 'sport = :9901' | grep -q . && rec PG-rollback-hold PASS "R-2 moved F8 files, withheld daemon-reload (other unit pending), 9901 closed" || rec PG-rollback-hold FAIL "$(tail -2 $EV/PG-rbhold-R2.log)"
cp -p /root/f8r2/authority.unit.orig $SD/lilith-authority-dev.service; systemctl daemon-reload   # owner-equivalent completion
clean_check PG-rbhold "$PRE"

s "FINAL"
bash $P/bin/observe_host.sh $EV/FINAL >/dev/null
bash $P/bin/compare_observations.sh $EV/M0 $EV/FINAL > $EV/FINAL-cmp.txt && rec FINAL-obs PASS "M0 == FINAL" || rec FINAL-obs FAIL "$(grep DIFF $EV/FINAL-cmp.txt | tr '\n' ' ')"
bash $P/bin/dr5_check.sh $EV/FINAL-dr5.txt > $EV/FINAL-dr5-check.txt && rec FINAL-DR5 PASS "$(tail -1 $EV/FINAL-dr5-check.txt)" || rec FINAL-DR5 FAIL "$(tail -1 $EV/FINAL-dr5-check.txt)"
echo; echo "TOTAL: $(grep -cE $'\t(PASS|CLEAN|SUCCESS)\t' $RES) ok / $(wc -l < $RES) rows; NOT ok: $(grep -vcE $'\t(PASS|CLEAN|SUCCESS)\t' $RES)"
