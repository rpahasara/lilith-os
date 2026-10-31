#!/usr/bin/env bash
# Runs the REAL window scripts, in order and with faults, in a disposable Linux root, against fake_core.py. test_auth_stages.py proves the same decisions on the real app.
# Stubbed: Core API, the gate, sudo, systemctl, journalctl, hostname, ss, ip, sleep and the gateway turn. Real: curl, the scripts, the database digest.
#   bash window_sim_auth.sh <package> <app dir, new> <app dir, previous> <post-bootstrap db> <venv python>
set -u
PKG=$1; NEWAPP=$2; OLDAPP=$3; POSTDB=$4; PY=$5; FAKE=$PKG/tests/fake_core.py
case "$(cat /etc/hostname 2>/dev/null)" in lilith-*) echo "REFUSED on a lilith host"; exit 9;; esac
NICIP=$(hostname -I | awk '{print $1}'); [ -n "$NICIP" ] || { echo "no NIC address"; exit 9; }
TOP=$(mktemp -d /tmp/authsim.XXXXXX); BIN=$TOP/bin; mkdir -p "$BIN"
cat > "$BIN/hostname" <<'E'
#!/bin/bash
echo lilith-dev-01
E
cat > "$BIN/sleep" <<'E'
#!/bin/bash
/usr/bin/sleep 0.2
E
cat > "$BIN/chown" <<'E'
#!/bin/bash
exit 0
E
cat > "$BIN/pgrep" <<'E'
#!/bin/bash
echo 0
E
cat > "$BIN/ip" <<E
#!/bin/bash
echo "2: eth0 inet $NICIP/20 scope global"
E
cat > "$BIN/ss" <<'E'
#!/bin/bash
case "$*" in *9911*) [ -e "$S/gate_down" ] || echo "LISTEN 0 5 127.0.0.1:9911 0.0.0.0:*";; *8765*) echo "LISTEN 0 2048 0.0.0.0:8765 0.0.0.0:*";; *-Hltnp*) echo "LISTEN python";; esac
exit 0
E
cat > "$BIN/journalctl" <<'E'
#!/bin/bash
case "$*" in *hermes-provider-gate-dev*) cat "$S/gate.journal";; *) /usr/bin/python3 -I -c 'import sys,re,datetime
m=sys.argv[2:]
print(open(sys.argv[1],errors="replace").read()[int(open(sys.argv[1]+".mark").read() or 0):],end="")' "$S/api.log" x;; esac
E
cat > "$BIN/sudo" <<'E'
#!/bin/bash
[ "$1" = -n ] && shift
[ "$1" = -u ] && shift 2
turn() {
  cat >/dev/null; msg=$1; ses=$2; echo "$msg" >> "$S/sent"
  rec() { printf '%s\n' "$1" >> "$DLOG"; }
  case "$msg" in
   *options*) rec '{"ts":1,"chat_id":"'$ses'","lane":"motivation","motivation_mode":"shadow","trace":{"highest_intensity_class":"SATISFIED","satisfied_drive_types":["COHERENCE","GOAL_COMPLETION"]}}'
     rec '{"ts":1,"chat_id":"'$ses'","lane":"workspace","workspace_mode":"shadow","trace":{"deciding_rule":"NO_CANDIDATE","candidate_count":0}}'
     for p in '/os/goals?limit=200' /os/goals/focus '/os/drafts?limit=200' '/os/tasks?limit=200' '/os/world?entity_type=career.application&entity_id=14'; do /usr/bin/curl -s -o /dev/null "http://127.0.0.1:8765$p"; done
     rec '{"ts":1,"chat_id":"'$ses'","lane":"reasoning","reasoning_mode":"shadow","intent":{"mode":"OPTION_GENERATION","app_id":null},"trace":null}'
     rec '{"ts":1,"chat_id":"'$ses'","lane":"cognitive","cognitive_mode":"shadow"}';;
  esac
  rec '{"ts":1,"chat_id":"'$ses'","mode":"social","live":false}'
  if [ -e "$S/gate_down" ]; then echo "TURN_RESULT 200 completed 42"; else read -r u l < "$S/budget"; echo "$((u+1)) $l" > "$S/budget"; echo T >> "$LEDGER"; echo '{"decision": "FORWARDED"}' >> "$S/gate.journal"; echo "TURN_RESULT 200 completed 42"; fi
  exit 0
}
case "$*" in *b4.started*) case "$1" in touch) stat -c %s "$S/api.log" > "$S/api.log.mark";; esac;; esac
case "$1" in
 python3) if [ "$2 $3" = "-I -" ] && [ $# -eq 5 ] && [[ "$4" != /* ]]; then turn "$4" "$5"; fi; shift; exec /usr/bin/python3 "$@";;
 *) exec "$@";;
esac
E
cat > "$BIN/systemctl" <<'E'
#!/bin/bash
cmd=$1; shift
start_api() {
  [ -e "$S/api.pid" ] && kill "$(cat "$S/api.pid")" 2>/dev/null
  for _ in 1 2 3 4 5 6 7 8 9 10; do /usr/bin/curl -s -o /dev/null -m 1 http://127.0.0.1:8765/health || break; /usr/bin/sleep 0.2; done
  rel=$(readlink -f "$APPROOT/current")
  [ "${INJECT:-}" = new_no_start ] && [ "$rel" = "$(cat "$S/newrel")" ] && [ -e "$F" ] && grep -q 'READ_AUTH=enforced' "$F" && exit 1
  [ "${INJECT:-}" = old_no_start ] && [ "$rel" != "$(cat "$S/newrel")" ] && [ -e "$S/armed" ] && exit 1
  stat -c %s "$S/api.log" > "$S/api.log.mark"
  ( cd "$(readlink -f "$APPROOT/current")"; set -a; LILITH_DB_PATH=$DBPATH; LILITH_DATA_DIR=$DATA_DIR
    if [ -e "$F" ]; then eval "$(sed -n 's/^Environment="\(.*\)"$/export \1/p' "$F")"; f=$(sed -n 's/^EnvironmentFile=//p' "$F"); [ -n "$f" ] && . "$f"; fi
    set +a; exec /usr/bin/python3 -u "$FAKE" >> "$S/api.log" 2>&1 ) &
  echo $! > "$S/api.pid"; echo $! >> "$S/api.pids"
}
case $cmd in
 list-units|daemon-reload) exit 0;;
 restart) start_api; exit 0;;
 stop) touch "$S/gate_down"; exit 0;;
 start) rm -f "$S/gate_down"; exit 0;;
 show) ;;
esac
unit=${1%.service}; shift; props=; value=
while [ $# -gt 0 ]; do case $1 in -p) props="$props ${2//,/ }"; shift 2;; --value) value=1; shift;; *) shift;; esac; done
for p in $props; do
 case "$unit:$p" in
  hermes-provider-gate-dev:ActiveState) if [ -e "$S/gate_down" ]; then v=inactive; else v=active; fi;;
  hermes-gateway-dev:MainPID) v=407521;;
  lilith-os-api-dev:MainPID) v=$(cat "$S/api.pid");;
  lilith-os-api-dev:Environment) v="LILITH_DB_PATH=$DBPATH"; [ -e "$F" ] && v="$v $(sed -n 's/^Environment="\(.*\)"$/\1/p' "$F" | tr '\n' ' ')";;
  *:DropInPaths) v="";;
  *:ActiveState) v=active;;
  *:MainPID) v=1;; *) v=x;;
 esac
 if [ -n "$value" ]; then echo "$v"; else echo "$p=$v"; fi
done
E
chmod +x "$BIN"/*
ORIG=$PATH
PASSN=0; FAILN=0
ok() { if [ "$2" = "$3" ]; then PASSN=$((PASSN+1)); echo "  PASS $1"; else FAILN=$((FAILN+1)); echo "  FAIL $1: got '$2' want '$3'"; fi; }
rw() { sed -e "s#/opt/hermes-gateway-dev#$R/opt/hermes-gateway-dev#g" -e "s#/home/lilith#$R/home/lilith#g" -e "s#/root/#$R/root/#g" -e "s#/var/lib/hermes-forget#$R/var/lib/hermes-forget#g" -e "s#/var/lib/private#$R/var/lib/private#g" -e "s#/etc/#$R/etc/#g" \
  -e "s#http://127.0.0.1:9911/healthz#http://127.0.0.1:19911/healthz#g" -e "s#NIC=10.20.0.3#NIC=$NICIP#" -e "s#5764da8e26246d16#$LSHA#g" -e "s#sudo -n sed -n#sed -n#g" "$1"; }
setup() {
  [ -n "${S:-}" ] && [ -e "$S/api.pid" ] && kill "$(cat "$S/api.pid")" 2>/dev/null; /usr/bin/sleep 0.5
  R=$TOP/$1; S=$R/state; mkdir -p "$S" "$R/run"; export INJECT=${2:-}
  HH=$R/home/lilith/.hermes-dev; APPROOT=$R/home/lilith/.hermes/lilith-os-dev; mkdir -p "$HH/logs" "$HH/sessions" "$APPROOT/releases/old" "$APPROOT/releases/new" "$APPROOT/data" "$R/opt/hermes-gateway-dev/releases/f293e72-f9c2-cog1-wm1-g1-r1-w1-m1-p1-e1" "$R/var/lib/hermes-forget/intent" "$R/var/lib/private/hermes-provider-gate-dev" "$R/etc/systemd/system" "$R/root"
  cp -r "$OLDAPP"/. "$APPROOT/releases/old/"; cp -r "$NEWAPP"/. "$APPROOT/releases/new/"
  ln -s "$R/opt/hermes-gateway-dev/releases/f293e72-f9c2-cog1-wm1-g1-r1-w1-m1-p1-e1" "$R/opt/hermes-gateway-dev/current"
  ln -s "$APPROOT/releases/old" "$APPROOT/current"; echo "$APPROOT/releases/new" > "$S/newrel"
  DBPATH=$APPROOT/data/lilith-dev.db; DATA_DIR=$APPROOT/data; cp "$POSTDB" "$DBPATH"
  LEDGER=$R/var/lib/private/hermes-provider-gate-dev/ledger.log; seq 1 29 | sed 's/^/LINE /' > "$LEDGER"; LSHA=$(sha256sum "$LEDGER" | cut -c1-16)
  for d in $(seq 1 28); do echo x > "$HH/sessions/request_dump_$d"; done
  DLOG=$HH/logs/lilith-router-decisions.log; : > "$DLOG"; : > "$S/api.log"; : > "$S/gate.journal"; : > "$S/sent"; echo "3 5" > "$S/budget"
  PORTX=911; F=$R/etc/systemd/system/lilith-os-api-dev.service.d/auth.conf
  for s in "$PKG"/scripts/*.sh "$PKG"/tests/prior/*.sh; do rw "$s" > "$R/run/$(basename "$s")"; done
  export FAKE S R PY APPROOT F DBPATH DATA_DIR LEDGER DLOG; export PATH=$BIN:$ORIG
  systemctl restart lilith-os-api-dev; for _ in $(seq 1 40); do /usr/bin/curl -s -o /dev/null -m 1 http://127.0.0.1:8765/health && break; /usr/bin/sleep 0.25; done
}
step() { local n=$1; ( cd "$R"; bash -c "test \"\$(hostname)\" = lilith-dev-01 || exit 97; $(cat "$R/run/$n")" ) > "$R/out.$n" 2>&1; grep -hE "^(CHECK_FAIL|[A-Z0-9]+_[A-Z0-9_]+ (PASS|FAIL))" "$R/out.$n" | tail -4 | cut -c1-130 | sed "s/^/    $n /"; }
got() { grep -c "^$2 PASS" "$R/out.$1"; }
deploy() { ln -sfn "$APPROOT/releases/new" "$APPROOT/current"; systemctl restart lilith-os-api-dev; for _ in $(seq 1 40); do /usr/bin/curl -s -o /dev/null -m 1 http://127.0.0.1:8765/health && break; /usr/bin/sleep 0.25; done; }
upto() { for pair in "$@"; do step "${pair%%:*}.sh"; done; }

echo "== happy path"; setup pass
sed -i 's/want no_local_proxy .*/true/; s/want no_failed_units .*/true/' "$R"/run/*.sh
step a0_preflight_ro.sh; ok "A0" "$(got a0_preflight_ro.sh A0_PREFLIGHT)" 1
step a1_dropin_open.sh; ok "A1" "$(got a1_dropin_open.sh A1_DROPIN)" 1
deploy
resume() { step b0_verify_deploy_ro.sh; step b1_tokens.sh; rm -f "$R/root/auth-window-20261101/b1.pass"; step rb_restore_previous.sh; step c0_resume_preflight_ro.sh; [ "${LATE:-}" = 1 ] && export INJECT=new_500; step b1b_resume_new.sh; }
resume; ok "RECOVERED_STATE" "$(got rb_restore_previous.sh RB_RESTORE)" 1; ok "C0" "$(got c0_resume_preflight_ro.sh C0_RESUME)" 1; ok "B1B" "$(got b1b_resume_new.sh B1B_RESUME)" 1
for pair in b2_enforce_write:B2_WRITE b3_enforce_read:B3_READ b4_router_turns:B4_TURNS b5_rollback_proof:B5_ROLLBACK b6_final_ro:B6_FINAL; do step "${pair%%:*}.sh"; ok "${pair##*:}" "$(got "${pair%%:*}.sh" "${pair##*:}")" 1; done
ok "no token in any step output" "$(cat "$R"/out.* | grep -cFf <(sed -n 's/^[A-Z_]*=//p' "$R/etc/lilith-os-api-dev/auth.env"))" 0
ok "no token in any script as run" "$(cat "$R"/run/* | grep -cFf <(sed -n 's/^[A-Z_]*=//p' "$R/etc/lilith-os-api-dev/auth.env"))" 0
ok "no token in the drop-in" "$(grep -cFf <(sed -n 's/^[A-Z_]*=//p' "$R/etc/lilith-os-api-dev/auth.env") "$F")" 0
ok "no token in the access log" "$(grep -cFf <(sed -n 's/^[A-Z_]*=//p' "$R/etc/lilith-os-api-dev/auth.env") "$S/api.log")" 0
ok "tokens 2 lines" "$(wc -l < "$R/etc/lilith-os-api-dev/auth.env")" 2
step m1_model_turns.sh; ok "M1" "$(got m1_model_turns.sh M1_MODEL)" 1
ok "budget ends 5/5" "$(cat "$S/budget")" "5 5"
ok "ledger 31" "$(wc -l < "$LEDGER")" 31

echo "== second runs refuse"
step m1_model_turns.sh; ok "M1 refuses a second run" "$(grep -c 'M1_ABORTED already ran' "$R/out.m1_model_turns.sh")" 1
step b5_rollback_proof.sh; ok "B5 refuses a second run" "$(grep -c 'B5_ABORTED already ran' "$R/out.b5_rollback_proof.sh")" 1
step b4_router_turns.sh; ok "B4 refuses a second run" "$(grep -c 'B4_ABORTED already ran' "$R/out.b4_router_turns.sh")" 1

echo "== guards"; setup noauthcode
sed -i 's/want no_local_proxy .*/true/; s/want no_failed_units .*/true/' "$R"/run/*.sh
step a1_dropin_open.sh
step b0_verify_deploy_ro.sh; ok "B0 fails if the merged code never arrived" "$(grep -c '^B0_VERIFY FAIL' "$R/out.b0_verify_deploy_ro.sh")" 1
step b1b_resume_new.sh; ok "B1B refuses without B0" "$(grep -c 'B1B_ABORTED B0 did not pass' "$R/out.b1b_resume_new.sh")" 1
echo extra >> "$LEDGER"; step c0_resume_preflight_ro.sh; ok "C0 fails on a moved ledger" "$(grep -c '^C0_RESUME FAIL' "$R/out.c0_resume_preflight_ro.sh")" 1
step ra_remove_dropin.sh; ok "RA removes the drop-in" "$(test -e "$F" && echo y || echo n)$(got ra_remove_dropin.sh RA_REMOVE)" n1

on_old() { test "$(readlink -f "$APPROOT/current")" = "$APPROOT/releases/old" && echo old || echo new; }
nic() { /usr/bin/curl -s -o /dev/null -w '%{http_code}' "http://$NICIP:8765/os/goals?limit=1"; }
fresh() { sed -i 's/want no_local_proxy .*/true/; s/want no_failed_units .*/true/' "$R"/run/*.sh; step a1_dropin_open.sh; deploy; }

echo "== recovery from enforced"; setup recover; fresh
resume; upto b2_enforce_write b3_enforce_read
step rb_restore_previous.sh; ok "RB restores the previous release" "$(got rb_restore_previous.sh RB_RESTORE)$(on_old)$(nic)" 1old200
ok "RB leaves no enforcement in the drop-in" "$(grep -c 'enforced\|EnvironmentFile\|TRUST_LOOPBACK' "$F")" 0
ok "RB keeps the database" "$(grep -c '^OK_DB' "$R/out.rb_restore_previous.sh")" 1

echo "== new code unhealthy on resume"; setup unhealthy; fresh
LATE=1; resume; LATE=; ok "B1B fails on unhealthy new code" "$(grep -c '^B1B_RESUME FAIL' "$R/out.b1b_resume_new.sh")" 1
step rb_restore_previous.sh; ok "RB leaves the unhealthy code" "$(got rb_restore_previous.sh RB_RESTORE)$(on_old)$(nic)" 1old200

echo "== new code won't start under enforcement"; setup nostart new_no_start; fresh
resume; upto b2_enforce_write b3_enforce_read
ok "B3 fails when Core API won't start" "$(grep -c '^B3_READ FAIL' "$R/out.b3_enforce_read.sh")" 1
step rb_restore_previous.sh; ok "RB recovers a dead new release" "$(got rb_restore_previous.sh RB_RESTORE)$(on_old)$(nic)" 1old200

echo "== rollback fails midway"; setup midway; fresh
resume; upto b2_enforce_write b3_enforce_read b4_router_turns
sed -i 's/^link "${NEW}"$/link "\/nonexistent"/' "$R/run/b5_rollback_proof.sh"; step b5_rollback_proof.sh
ok "B5 fails midway" "$(grep -c '^B5_ROLLBACK FAIL' "$R/out.b5_rollback_proof.sh")" 1
step rb_restore_previous.sh; ok "RB recovers from a broken link" "$(got rb_restore_previous.sh RB_RESTORE)$(on_old)$(nic)" 1old200

echo "== previous release won't start"; setup oldfail old_no_start; fresh
resume; touch "$S/armed"
step rb_restore_previous.sh; ok "RB says so when the previous release can't start" "$(grep -c '^RB_RESTORE FAIL' "$R/out.rb_restore_previous.sh")" 1
touch "$S/x"; rm -f "$S/armed"

echo "== no recorded previous release"; setup nowindow
step rb_restore_previous.sh; ok "RB refuses with nothing recorded" "$(grep -c 'RB_ABORTED' "$R/out.rb_restore_previous.sh")" 1

[ -e "$S/api.pid" ] && kill "$(cat "$S/api.pid")" 2>/dev/null
echo "AUTH_SIM checks pass=$PASSN fail=$FAILN"
[ "$FAILN" -eq 0 ] && echo "AUTH_SIM PASS" || echo "AUTH_SIM FAIL"
[ -n "${KEEP:-}" ] || rm -rf "$TOP"
