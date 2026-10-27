#!/usr/bin/env bash
# F9-C executor: REAL systemd mirror layer (WSL only; refused on lilith-dev-01). Installs the real path / executor /
# restart units, tmpfiles and gateway drop-in, plus MIRROR-ONLY stand-ins (a gateway stand-in in the real gateway
# sandbox, a sandbox probe with the executor's exact sandbox). Runs probes P-1/P-2 and scenarios M1 (end to end),
# M5 (start limit), M3 (SIGKILL mid-erasure) and M6 (locked store, fail closed). Saves and restores the pre-existing
# HERMES_HOME, backups and data files exactly. Synthetic data only; no provider; nothing touches DEV.
set -uo pipefail
[[ $(hostname) != lilith-dev-01 ]] || { echo "refused on lilith-dev-01"; exit 1; }
X=/root/f9ca/tracka; PK=$X/pkgfiles; MI=$X/mirror; F9B=/root/f9b/build/pkg
CORE_SRC=/root/f9ca/repo/services/core-api; CORE=/opt/lilith-os-dev-mirror/core-api; LIB=/usr/local/lib/f9c4-mirror
HH=/home/lilith/.hermes-dev; DATA=/home/lilith/.hermes/lilith-os-dev/data; B=/var/backups/hermes-gateway-dev
SAVE=/var/tmp/f9c4-saved; RES=/root/f9ca/mirror-results.tsv; EV=/root/f9ca/mirror-ev; : > $RES; rm -rf $EV; mkdir -p $EV
MID=$(cat /etc/machine-id); JD=/var/log/journal/$MID.hermes-gateway-dev; SD=/etc/systemd/system
MARK=/var/lib/hermes-forget/in-progress; CAN=F9C-MIRROR-CANARY
rec() { printf '%s\t%s\t%s\n' "$1" "$2" "$3" | tee -a $RES; }
[[ ! -e $SAVE ]] || { echo "previous mirror save present at $SAVE: restore it first"; exit 1; }
mkdir -p $SAVE
CREATED=$SAVE/created; : > $CREATED

teardown() {
  systemctl stop hermes-forget.path hermes-forget-reconcile.timer hermes-forget-reconcile.service \
    hermes-forget-executor.service hermes-forget-restart.service \
    hermes-gateway-dev.service f9c4-sandbox-probe.service 2>/dev/null
  systemctl stop systemd-journald@hermes-gateway-dev.socket systemd-journald-varlink@hermes-gateway-dev.socket \
    systemd-journald@hermes-gateway-dev.service 2>/dev/null
  rm -f $SD/hermes-forget-executor.service $SD/hermes-forget.path $SD/hermes-forget-restart.service \
    $SD/hermes-forget-reconcile.service $SD/hermes-forget-reconcile.timer \
    $SD/hermes-gateway-dev.service $SD/f9c4-sandbox-probe.service
  rm -rf $SD/hermes-gateway-dev.service.d /etc/systemd/journald@hermes-gateway-dev.conf /etc/tmpfiles.d/hermes-forget.conf
  rm -rf /etc/hermes-forget /etc/lilith-os-dev /run/hermes-forget /var/lib/hermes-forget /opt/hermes-gateway-dev \
    /opt/lilith-os-dev-mirror $LIB "$JD" /tmp/f9c4-m6
  while read -r p; do rm -rf "$p"; done < $CREATED
  rm -rf "$HH" "$B"; rm -f $DATA/privacy_governance.dev.db* $DATA/cognitive_memory.dev.db
  [[ -d $SAVE/hermes-dev ]] && mv $SAVE/hermes-dev "$HH"
  [[ -d $SAVE/backups ]] && mv $SAVE/backups "$B"
  gpasswd -d lilith lilith-forget >/dev/null 2>&1; groupdel lilith-forget 2>/dev/null
  systemctl daemon-reload; systemctl reset-failed 2>/dev/null
  rm -rf $SAVE
  echo "TEARDOWN home=[$(ls -A $HH | tr '\n' ' ')] backups=[$(ls -A $B | tr '\n' ' ')] data=[$(ls -A $DATA | tr '\n' ' ')]"
}
trap teardown EXIT

# ------------------------------------------------------------------------------------------------------- setup ---
mv "$HH" $SAVE/hermes-dev; [[ -d $B ]] && mv "$B" $SAVE/backups
groupadd -f lilith-forget; usermod -aG lilith-forget lilith
REL=/opt/hermes-gateway-dev/releases/f9c4-mirror
mkdir -p $REL/bin; ln -s $F9B/python $REL/python; cp $PK/bin/hermes_forget_executor.py $PK/bin/hermes_restore_guard.py $REL/bin/
ln -sfn releases/f9c4-mirror /opt/hermes-gateway-dev/current
mkdir -p /opt/lilith-os-dev-mirror && cp -a $CORE_SRC $CORE && chmod -R a+rX /opt/lilith-os-dev-mirror
mkdir -p /etc/lilith-os-dev
(cd $CORE/tests && python3 -I -c "import sys; sys.path.insert(0,'.'); from test_privacy_hermes_owner_v2 import SECRET; sys.stdout.buffer.write(SECRET)") > /etc/lilith-os-dev/privacy-authority.key
chown root:lilith /etc/lilith-os-dev/privacy-authority.key; chmod 0640 /etc/lilith-os-dev/privacy-authority.key
runuser -u lilith -- python3 -c "import sqlite3
for p in ('$DATA/privacy_governance.dev.db', '$DATA/cognitive_memory.dev.db'):
    c = sqlite3.connect(p); c.execute('CREATE TABLE placeholder(x)'); c.commit(); c.close()"
chmod 0600 $DATA/privacy_governance.dev.db $DATA/cognitive_memory.dev.db
for d in /etc/hermes-gateway-dev /var/lib/lilith-memory-broker /etc/lilith-authority-dev; do
  [[ -e $d ]] || { mkdir -p $d; echo "$d" >> $CREATED; }
done
echo "F9C4_TEST_ONLY_PLACEHOLDER=1" > /etc/hermes-gateway-dev/provider.env; chmod 0600 /etc/hermes-gateway-dev/provider.env
echo probe > /var/lib/lilith-memory-broker/probe; echo probe > /etc/lilith-authority-dev/probe
cp $PK/systemd/hermes-forget.tmpfiles.conf /etc/tmpfiles.d/hermes-forget.conf
systemd-tmpfiles --create /etc/tmpfiles.d/hermes-forget.conf
mkdir -p /etc/hermes-forget
python3 - "$CORE/lilith_memory" > /etc/hermes-forget/executor.json <<PY
import hashlib, json, sys, grp, pwd
pkg = sys.argv[1]
mods = ("__init__.py", "canonical_contracts.py", "memory_action_v2.py", "canonical_authority.py", "privacy_governance.py")
print(json.dumps({
  "deploymentEnvironment": "DEV_SYNTHETIC", "hermesHome": "$HH", "spoolDir": "/run/hermes-forget/spool",
  "stateDir": "/var/lib/hermes-forget/state", "receiptDir": "/var/lib/hermes-forget/receipts",
  "receiptGid": grp.getgrnam("lilith-forget").gr_gid, "epochLog": "/var/lib/hermes-forget/epochs/epochs.log",
  "inProgressMarker": "$MARK", "backupRoot": "$B", "journalNamespace": "hermes-gateway-dev", "journalDir": "$JD",
  "gatewayUnit": "hermes-gateway-dev.service", "gatewayPorts": [9901], "requesterUid": pwd.getpwnam("lilith").pw_uid,
  "privacyDb": "$DATA/privacy_governance.dev.db", "privacySecret": "/etc/lilith-os-dev/privacy-authority.key",
  "coreApiDir": pkg, "coreApiSha256": {m: hashlib.sha256(open(f"{pkg}/{m}", "rb").read()).hexdigest() for m in mods},
}, indent=1))
PY
chmod 0644 /etc/hermes-forget/executor.json
cp $PK/systemd/hermes-forget-executor.service $PK/systemd/hermes-forget.path $PK/systemd/hermes-forget-restart.service \
   $PK/systemd/hermes-forget-reconcile.service $PK/systemd/hermes-forget-reconcile.timer $SD/
mkdir -p $SD/hermes-gateway-dev.service.d && cp $PK/systemd/hermes-gateway-dev.service.d/50-forget.conf $SD/hermes-gateway-dev.service.d/
cp $F9B/systemd/journald@hermes-gateway-dev.conf /etc/systemd/
mkdir -p $LIB && cp $MI/gateway_standin.py $MI/sandbox_probe.py $MI/test_f9c4_mirror_e2e.py $LIB/ && chmod -R a+rX $LIB
# Gateway stand-in = the REAL package gateway unit (whole sandbox) with only ExecStart/ExecStartPre/venv condition swapped.
sed -e '/^ConditionPathExists=\/opt\/hermes-gateway-dev\/current\/venv/d' -e '/^ExecStartPre=/d' \
    -e "s|^ExecStart=.*|ExecStart=/usr/bin/python3 -I -B $LIB/gateway_standin.py -m hermes_cli.main gateway run|" \
    $F9B/systemd/hermes-gateway-dev.service > $SD/hermes-gateway-dev.service
# Sandbox probe = the executor unit's exact [Service] sandbox with only ExecStart swapped (no lifecycle lines).
sed -e '/^Conflicts=/d' -e '/^After=/d' -e '/^OnSuccess=/d' -e '/^ConditionPathExists=/d' \
    -e "s|^ExecStart=.*|ExecStart=/usr/bin/python3 -I -B $LIB/sandbox_probe.py|" \
    $PK/systemd/hermes-forget-executor.service > $SD/f9c4-sandbox-probe.service
systemctl daemon-reload
systemctl start hermes-forget-reconcile.timer
systemctl start hermes-forget.path && rec setup PASS "units installed; path unit $(systemctl is-active hermes-forget.path)" || { rec setup FAIL ""; exit 1; }

fixture() { F9C_LILITH_UID=$(id -u lilith) F9C_LILITH_GID=$(id -g lilith) python3 -I $MI/build_fixture.py $F9B/src $F9B/home "$HH" "$B" >/dev/null; }
wait_port() { for _ in $(seq 1 60); do ss -Hltn 'sport = :9901' | grep -q . && return 0; sleep 1; done; return 1; }
wait_active() { for _ in $(seq 1 60); do [[ $(systemctl is-active hermes-gateway-dev) == active ]] && wait_port && return 0; sleep 1; done; return 1; }
core_as_lilith() {  # <test selector> : the Core API runner as uid lilith
  runuser -u lilith -- env -C $LIB HOME=/tmp PYTHONDONTWRITEBYTECODE=1 F9C_CORE_API=$CORE F9C_TIMEOUT=${F9C_TIMEOUT:-240} \
    F9C_SIGNAL_DIR=/tmp/f9c4-m6 python3 -B -m unittest "$@" 2>&1; }
scan() { grep -rl "$CAN" "$HH" "$B" /var/lib/hermes-forget /run/hermes-forget 2>/dev/null | wc -l; }
journal_before() { journalctl --namespace=hermes-gateway-dev --until="$1" -o cat --no-pager 2>/dev/null | grep -c "$CAN"; }
exec_start() { systemctl show hermes-forget-executor -p ExecMainStartTimestamp --value; }

# -------------------------------------------------------------------------------- P-1 executor sandbox probe ---
fixture                                  # the executor unit requires HERMES_HOME to exist (ReadWritePaths without -)
systemctl start f9c4-sandbox-probe.service
P1=$(journalctl -u f9c4-sandbox-probe -o cat --no-pager | grep '^PROBE' | tail -1); echo "$P1" > $EV/P1.txt
exp="authority_read=ABSENT broker_read=ABSENT code_write=EROFS cognitive_read=ABSENT coreapi_db_read=ABSENT etc_write=EROFS hermes_home_write=WRITE net_external=BLOCKED net_metadata=BLOCKED privacy_read=READ privacy_write=EROFS provider_key_read=ABSENT state_write=WRITE sudoers_read=ABSENT"
norm() { tr ' ' '\n' | sed -e 's/=DENIED$/=ABSENT/' -e 's/=HIDDEN$/=ABSENT/' | sort | paste -sd' '; }
[[ $(echo "${P1#PROBE }" | norm) == $(echo "$exp" | norm) ]] && rec P-1 PASS "executor sandbox: $P1" || rec P-1 FAIL "got: $P1 | expected (DENIED==ABSENT): $exp"

# ---------------------------------------------------------------------------- P-2 gateway cannot see the spool ---
fixture
systemctl start hermes-gateway-dev; wait_active || rec P-2 FAIL "stand-in not up"
P2=$(journalctl --namespace=hermes-gateway-dev -o cat --no-pager | grep '^PROBE' | tail -1); echo "$P2" > $EV/P2.txt
echo "$P2" | grep -Eq '=(VISIBLE|WRITABLE)' && rec P-2 FAIL "gateway sees erasure paths: $P2" || rec P-2 PASS "T6 gateway sandbox: $P2"

# ---------------------------------------------------------------------------------------- M1 end to end (T1) ---
SOUL0=$(sha256sum < $HH/SOUL.md)
[[ $(journal_before now) -gt 0 ]] && rec M1-pre PASS "canary present in namespace journal + $(scan) host files before" || rec M1-pre FAIL "no canary to erase"
core_as_lilith test_f9c4_mirror_e2e.MirrorEndToEnd.test_forget_through_the_installed_executor > $EV/M1.log
grep -q 'MIRROR_RESULT status=COMPLETE' $EV/M1.log && rec M1 PASS "$(grep MIRROR_RESULT $EV/M1.log)" || rec M1 FAIL "$(tail -5 $EV/M1.log | tr '\n' ' ')"
T1=$(exec_start)
rec M1-exec INFO "executor Result=$(systemctl show hermes-forget-executor -p Result --value) start=[$T1]"
wait_active && rec M1-restart PASS "gateway restarted by OnSuccess (start limit reset)" || rec M1-restart FAIL "gateway not active"
R=$(ls /var/lib/hermes-forget/receipts/*.receipt.json 2>/dev/null | head -1)
[[ -n $R && $(stat -c '%U:%G %a' "$R") == "root:lilith-forget 640" ]] && rec M1-receipt PASS "$(stat -c '%U:%G %a' "$R") $(python3 -c "import json,sys;d=json.load(open(sys.argv[1]));print(d['status'],d['erasureEpoch'],d['claim'],d['providerErasure'])" "$R")" || rec M1-receipt FAIL "$R"
[[ $(journal_before "$T1") -eq 0 ]] && rec M1-journal PASS "no canary entry older than the executor start remains in the namespace journal" || rec M1-journal FAIL "$(journal_before "$T1") canary entries survive"
N=$(scan); [[ $N -eq 0 ]] && rec M1-scan PASS "T19 canary 0 in HERMES_HOME, backups, executor state/spool" || rec M1-scan FAIL "$N files: $(grep -rl "$CAN" "$HH" "$B" /var/lib/hermes-forget 2>/dev/null | head -5 | tr '\n' ' ')"
[[ $(sha256sum < $HH/SOUL.md) == "$SOUL0" && -f $B/rollback-20261024T000000Z/opt/hermes-gateway-dev/src/gateway/run.py ]] \
  && rec M1-protected PASS "SOUL.md unchanged; backup code kept" || rec M1-protected FAIL ""
[[ ! -e $MARK ]] && rec M1-marker PASS "marker cleared" || rec M1-marker FAIL "marker present"
rec M1-epoch INFO "$(cat /var/lib/hermes-forget/epochs/epochs.log | wc -l) epoch line(s); executor log: $(journalctl -u hermes-forget-executor -o cat --no-pager | grep -c '"event"') events, canary $(journalctl -u hermes-forget-executor -o cat --no-pager | grep -c "$CAN")"

# --------------------------------------------------------------------------------- M5 start limit hit (T14) ---
fixture
for _ in $(seq 1 6); do systemctl restart hermes-gateway-dev 2>/dev/null || break; sleep 1; done
RES5=$(systemctl show hermes-gateway-dev -p Result --value)
rec M5-pre INFO "gateway Result=$RES5 ActiveState=$(systemctl is-active hermes-gateway-dev)"
core_as_lilith test_f9c4_mirror_e2e.MirrorEndToEnd.test_forget_through_the_installed_executor > $EV/M5.log
grep -q 'MIRROR_RESULT status=COMPLETE' $EV/M5.log && rec M5 PASS "FORGET complete with the gateway at its start limit" || rec M5 FAIL "$(tail -5 $EV/M5.log | tr '\n' ' ')"
wait_active && rec M5-restart PASS "reset-failed + start brought the gateway back" || rec M5-restart FAIL "$(systemctl show hermes-gateway-dev -p Result,ActiveState --value | paste -sd' ')"

# ------------------------------------------------------------------------------- M3 SIGKILL mid-erasure (T7) ---
fixture; systemctl reset-failed hermes-gateway-dev; systemctl start hermes-gateway-dev; wait_active
core_as_lilith test_f9c4_mirror_e2e.MirrorEndToEnd.test_forget_through_the_installed_executor > $EV/M3.log &
CP=$!
killed=0
for _ in $(seq 1 600); do
  if grep -lq '"FILES": "COMPLETE"' /var/lib/hermes-forget/state/*.json 2>/dev/null && [[ $(systemctl is-active hermes-forget-executor) == activating ]]; then
    systemctl kill -s KILL hermes-forget-executor.service && killed=1; break
  fi
  sleep 0.1
done
sleep 0.5
M3MARK=$([[ -e $MARK ]] && echo present || echo absent); M3GW=$(systemctl is-active hermes-gateway-dev)
wait $CP
rec M3-kill INFO "killed=$killed marker-after-kill=$M3MARK gateway-after-kill=$M3GW executor runs=$(journalctl -u hermes-forget-executor -o cat --no-pager | grep -c 'Starting\|"event"')"
grep -q 'MIRROR_RESULT status=COMPLETE' $EV/M3.log && [[ $killed == 1 && $M3MARK == present ]] \
  && rec M3 PASS "SIGKILL after FILES: marker kept, path unit re-ran the executor, FORGET COMPLETE" || rec M3 FAIL "killed=$killed marker=$M3MARK $(tail -3 $EV/M3.log | tr '\n' ' ')"
[[ $(scan) -eq 0 ]] && rec M3-scan PASS "canary 0 after resume" || rec M3-scan FAIL "$(scan) files"

# ---------------------------------------------------------------------- M6 locked store: fail closed (T9 real) ---
fixture; systemctl reset-failed hermes-gateway-dev; systemctl start hermes-gateway-dev; wait_active
rm -rf /tmp/f9c4-m6; mkdir -p /tmp/f9c4-m6; chown lilith /tmp/f9c4-m6
core_as_lilith test_f9c4_mirror_e2e.MirrorEndToEnd.test_locked_store_fails_closed_then_the_same_authorization_completes > $EV/M6.log &
CP=$!
for _ in $(seq 1 300); do [[ -e /tmp/f9c4-m6/failed ]] && break; sleep 1; done
systemctl start hermes-gateway-dev 2>/dev/null; sleep 2
M6GW="$(systemctl is-active hermes-gateway-dev) cond=$(systemctl show hermes-gateway-dev -p ConditionResult --value)"
M6EX=$(journalctl -u hermes-forget-executor -o cat --no-pager | grep -c STATE_DB_LOCKED)
touch /tmp/f9c4-m6/continue; wait $CP
rec M6-blocked INFO "gateway during failure: $M6GW; executor STATE_DB_LOCKED events=$M6EX"
grep -q 'MIRROR_RESUMED status=COMPLETE' $EV/M6.log && [[ $M6GW == "inactive cond=no" && $M6EX -ge 1 ]] \
  && rec M6 PASS "locked store: no receipt, gateway refused to start, same authorization completed on retry" \
  || rec M6 FAIL "$M6GW ex=$M6EX $(grep MIRROR_ $EV/M6.log | tr '\n' ' ')"
wait_active && rec M6-restart PASS "gateway back after the completed erasure" || rec M6-restart FAIL ""

# ------------------------------------- M7 finalization window: SIGKILL after the receipt, before Privacy completion ---
# The path unit is stopped so only the reconcile TIMER can heal; the executor is killed while it waits for Privacy
# after writing the receipt. The gateway must stay refused until Privacy itself shows completion.
fixture; systemctl reset-failed hermes-gateway-dev; systemctl start hermes-gateway-dev; wait_active
RC0=$(ls /var/lib/hermes-forget/receipts/*.receipt.json 2>/dev/null | wc -l)       # earlier scenarios' receipts
F9C_TIMEOUT=240 core_as_lilith test_f9c4_mirror_e2e.MirrorEndToEnd.test_forget_through_the_installed_executor > $EV/M7.log &
CP=$!
killed=0
for _ in $(seq 1 1200); do
  if [[ $(ls /var/lib/hermes-forget/receipts/*.receipt.json 2>/dev/null | wc -l) -gt $RC0 \
        && $(systemctl is-active hermes-forget-executor) == activating ]]; then           # THIS run's receipt
    systemctl stop hermes-forget.path
    systemctl kill -s KILL hermes-forget-executor.service && killed=1; break
  fi
  sleep 0.05
done
sleep 0.3
W_MARK=$([[ -e $MARK ]] && echo present || echo absent)
systemctl start hermes-gateway-dev 2>/dev/null; sleep 1
W_GW="$(systemctl is-active hermes-gateway-dev) cond=$(systemctl show hermes-gateway-dev -p ConditionResult --value)"
wait $CP
W_PY=$(grep -o 'MIRROR_RESULT status=[A-Z_]*' $EV/M7.log)
released=0; for _ in $(seq 1 120); do [[ ! -e $MARK ]] && [[ $(systemctl is-active hermes-gateway-dev) == active ]] && { released=1; break; }; sleep 1; done
rec M7-window INFO "killed=$killed marker-in-window=$W_MARK gateway-start-in-window=[$W_GW] privacy=[$W_PY] released-by-timer=$released reconcile-runs=$(journalctl -u hermes-forget-reconcile -o cat --no-pager | grep -c RECONCILED)"
[[ $killed == 1 && $W_MARK == present && $W_GW == "inactive cond=no" && $W_PY == "MIRROR_RESULT status=COMPLETE" && $released == 1 ]] \
  && rec M7 PASS "kill after receipt: gateway refused while Privacy incomplete; Privacy COMPLETE; reconcile timer released + restarted" \
  || rec M7 FAIL "killed=$killed mark=$W_MARK gw=[$W_GW] py=[$W_PY] released=$released"
rm -f /run/hermes-forget/spool/*.req; systemctl start hermes-forget.path

journalctl -u hermes-forget-executor -o cat --no-pager > $EV/executor-journal.txt
cp /var/lib/hermes-forget/epochs/epochs.log $EV/ 2>/dev/null
grep -c "$CAN" $EV/executor-journal.txt | xargs -I{} rec T24 INFO "executor journal canary hits={}"
echo "#### RESULTS"; cat $RES
