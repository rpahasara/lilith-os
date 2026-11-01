#!/usr/bin/env bash
# Runs the REAL guest_c1.sh, stage by stage and with faults, in a disposable root, against fake_core.py. TEST_ONLY.
# Stubbed: Core API, systemctl, journalctl, runuser, hostname, sleep, the deploy (a copy, as deploy_core_api_remote.sh would). Real: curl, the script, live_compare.py on real WAL databases.
#   bash sim_c1.sh <dir holding the package files, new app and old app>
set -u
SRC=$1
case "$(cat /etc/hostname 2>/dev/null)" in lilith-*) echo "REFUSED on a lilith host"; exit 9;; esac
[ "$(id -u)" = 0 ] || { echo "needs root"; exit 9; }
NIC=$(hostname -I | awk '{print $1}'); [ -n "$NIC" ] || { echo "no NIC"; exit 9; }
PASS=0; BAD=0
ok() { PASS=$((PASS+1)); echo "  PASS $1"; }
no() { BAD=$((BAD+1)); echo "  FAIL $1"; }
check() { if eval "$2"; then ok "$1"; else no "$1"; fi; }

setup() {
  TOP=$(mktemp -d /tmp/c1sim.XXXXXX); R=$TOP/root; S=$TOP/state; BIN=$TOP/bin
  mkdir -p "$BIN" "$S" "$R/var/tmp/c1" "$R/home/lilith/.hermes/lilith-os/api" "$R/home/lilith/.hermes/lilith-os/data" "$R/home/lilith/.hermes/memories" "$R/etc/systemd/system" "$R/root"
  H=$R/home/lilith/.hermes
  cp "$SRC/guest_c1.sh" "$SRC/live_compare.py" "$SRC/rehearsal_compare.py" "$R/var/tmp/c1/"
  cp "$SRC/app_old.py" "$H/lilith-os/api/app.py"
  printf 'TEST_ONLY soul\n' > "$H/SOUL.md"; printf 'TEST_ONLY user\n' > "$H/memories/USER.md"; printf 'x: 1\n' > "$H/config.yaml"
  for d in state.db lilith-os/data/lilith.db lilith-os/data/cognitive_memory.db lilith-os/data/privacy_governance.db; do
    python3 -I -c 'import sqlite3,sys; c=sqlite3.connect(sys.argv[1]); c.execute("PRAGMA journal_mode=WAL"); c.execute("CREATE TABLE t (a)"); c.execute("INSERT INTO t VALUES (1)"); c.commit(); c.close()' "$H/$d"
  done
  cat > "$BIN/hostname" <<E
#!/bin/bash
[ "\$1" = -I ] && echo "$NIC " || echo lilith-01
E
  printf '#!/bin/bash\n/usr/bin/sleep 0.1\n' > "$BIN/sleep"
  printf '#!/bin/bash\nshift 3\nexec "$@"\n' > "$BIN/runuser"
  cat > "$BIN/journalctl" <<E
#!/bin/bash
cat "$S/api.log" 2>/dev/null
E
  cat > "$BIN/systemctl" <<E
#!/bin/bash
S=$S; R=$R; H=$H; FAKE=$SRC/fake_core.py
cmd=\$1; shift
envs() { sed -n 's/^Environment="\(.*\)"\$/\1/p' "\$R/etc/systemd/system/lilith-os-api.service.d/auth.conf" 2>/dev/null; [ -f "\$R/etc/lilith-os-api/auth.env" ] && grep -q EnvironmentFile "\$R/etc/systemd/system/lilith-os-api.service.d/auth.conf" 2>/dev/null && cat "\$R/etc/lilith-os-api/auth.env"; }
start() {
  [ -e "\$S/api.pid" ] && kill "\$(cat "\$S/api.pid")" 2>/dev/null
  for _ in 1 2 3 4 5 6 7 8 9 10 11 12; do /usr/bin/curl -s -o /dev/null -m 1 http://127.0.0.1:8765/health || break; /usr/bin/sleep 0.2; done
  ( cd "\$H/lilith-os/api" && exec env -i PATH=/usr/bin:/bin S="\$S" INJECT="\$(cat "\$S/inject" 2>/dev/null)" \$(envs) python3 -I -B "\$FAKE" >> "\$S/api.log" 2>&1 ) &
  echo \$! > "\$S/api.pid"
}
case "\$cmd" in
 restart) case "\$1" in lilith-os-api*) start;; *) echo "\$1" >> "\$S/other_restart";; esac; for _ in 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15; do /usr/bin/curl -s -o /dev/null -m 1 http://127.0.0.1:8765/health && break; /usr/bin/sleep 0.2; done;;
 daemon-reload) ;;
 is-active) [ "\$1" = hermes-gateway.service ] && [ -e "\$S/gateway_down" ] && echo failed || echo active;;
 show) case "\$*" in *MainPID*ActiveState*|*ActiveState*MainPID*) echo "ActiveState=active"; echo "MainPID=77";; *MainPID*) cat "\$S/gwpid" 2>/dev/null || echo 77;; *Environment*) cat "\$S/unit_env" 2>/dev/null;; *) ;; esac;;
 --failed) cat "\$S/failed" 2>/dev/null;;
esac
E
  cat > "$BIN/fakedeploy" <<E
#!/bin/bash
# As deploy_core_api_remote.sh: back up, install, restart.
A=$H/lilith-os/api/app.py
cp "\$A" "\$A.bak.gitdeploy.20261101T000000Z"
cp "$SRC/app_new.py" "\$A"
systemctl restart lilith-os-api.service
E
  chmod +x "$BIN"/*
  OLD=$(sha256sum "$SRC/app_old.py" | cut -c1-64); NEW=$(sha256sum "$SRC/app_new.py" | cut -c1-64)
  SOUL=$(sha256sum "$H/SOUL.md" | cut -c1-64); USR=$(sha256sum "$H/memories/USER.md" | cut -c1-64)
  sed -i -e "s/^OLD_SHA=.*/OLD_SHA=$OLD/" -e "s/^NEW_SHA=.*/NEW_SHA=$NEW/" -e "s/^SOUL_SHA=.*/SOUL_SHA=$SOUL/" -e "s/^USER_SHA=.*/USER_SHA=$USR/" "$R/var/tmp/c1/guest_c1.sh"
  export PATH=$BIN:/usr/bin:/bin C1_ROOT=$R C1_PY=python3 C1_NIC=$NIC C1_TICK=0 C1_AS=env C1_OWNER=root
  systemctl restart lilith-os-api.service
}
down() { [ -e "$S/api.pid" ] && kill "$(cat "$S/api.pid")" 2>/dev/null; sleep 0.3; /usr/bin/sleep 0.5; rm -rf "$TOP"; }
g() { bash "$R/var/tmp/c1/guest_c1.sh" "$@" > "$S/last" 2>&1; }
last() { grep -q "$1" "$S/last"; }
win() { g w0 p0; g w0 pre; g w1; fakedeploy; g w2; g w3; g w4; }

echo "== whole window"
setup
g w0 p0; check 'preflight passes' 'last "^W0 PASS"'
g w0 p0; check 'preflight runs once' 'last "W0_ABORTED already ran"'
g w0 pre; check 'window baseline passes' 'last "^W0 PASS"'
g w1; check 'tokens and drop-in' 'last "^W1 PASS"'
check 'token file 600' '[ "$(stat -c %a $R/etc/lilith-os-api/auth.env)" = 600 ]'
check 'no token printed' '! grep -qE "[0-9a-f]{64}$" <(grep -v "^OK app\|^OK soul\|^OK user" $S/last)'
fakedeploy
g w2; check 'new code, open' 'last "^W2 PASS"'
check 'backup recorded' '[ -s $R/root/cutover1-20261101/backup ]'
g w3; check 'writes enforced' 'last "^W3 PASS"'; check 'router write reaches validation' 'last "OK router_write_reaches_validation"'
g w4; check 'reads enforced' 'last "^W4 PASS"'; check 'stranger refused on every route' '[ "$(grep -c "^OK stranger /" $S/last)" = 11 ]'
g w5; check 'nothing else moved' 'last "^W5 PASS"'; check 'judged equal' 'last "JUDGE_EQUAL"'
check 'gateway never restarted' '[ ! -e $S/other_restart ]'
cat $R/root/cutover1-20261101/*.pass >/dev/null
g rb; check 'return from the end' 'last "^RB_RESTORE PASS"'
check 'old code back' '[ "$(sha256sum $H/lilith-os/api/app.py | cut -c1-64)" = "$OLD" ]'
check 'return is timed' 'last "RETURN_SECONDS"'
check 'tokens kept for going forward' '[ -f $R/etc/lilith-os-api/auth.env ]'
down

echo "== preconditions stop with nothing changed"
setup; echo changed > "$H/lilith-os/api/app.py"; g w0 p0; check 'other app.py' 'last "^W0 FAIL"'; down
setup; echo changed >> "$H/SOUL.md"; g w0 p0; check 'other SOUL.md' 'last "^W0 FAIL"'; down
setup; echo changed >> "$H/memories/USER.md"; g w0 p0; check 'other USER.md' 'last "^W0 FAIL"'; down
setup; touch "$S/gateway_down"; g w0 p0; check 'gateway down' 'last "^W0 FAIL"'; down
setup; mkdir -p "$R/etc/systemd/system/lilith-os-api.service.d"; touch "$R/etc/systemd/system/lilith-os-api.service.d/auth.conf"; g w0 p0; check 'drop-in already there' 'last "^W0 FAIL"'; down
setup; echo 'LILITH_OS_WRITE_AUTH=x' > "$S/unit_env"; g w0 p0; check 'auth setting already there' 'last "^W0 FAIL"'; down
setup; rm "$H/config.yaml"; g w0 p0; check 'no settings file' 'last "^W0 FAIL"'; down
setup; g w0 pre; check 'window needs preflight' 'last "W0_ABORTED p0 did not run"'; down
setup; g w0 p0; echo 'y: 2' > "$H/config.yaml"; g w0 pre; check 'settings changed since preflight' 'last "^W0 FAIL"'; down
setup; g w1; check 'tokens need baseline' 'last "W1_ABORTED"'; down
setup; g w2; check 'stages keep their order' 'last "W2_ABORTED"'; down

echo "== failures during the window, each then returned"
setup; g w0 p0; g w0 pre; g w1; g w2; check 'deploy never happened' 'last "^W2 FAIL"'; g rb; check 'return with no deploy' 'last "^RB_RESTORE PASS"'; down
setup; g w0 p0; g w0 pre; g w1; fakedeploy; echo bad > "$H/lilith-os/api/app.py.bak.gitdeploy.20261101T000000Z"; g w2; check 'bad backup' 'last "^W2 FAIL"'; g rb; check 'no good backup: return says so' 'last "RB_RESTORE FAIL"'; down
setup; g w0 p0; g w0 pre; g w1; fakedeploy; g w2; g w3; echo new_500 > "$S/inject"; g w4; check 'new code errors under enforcement' 'last "^W4 FAIL"'; rm "$S/inject"; g rb; check 'returned' 'last "^RB_RESTORE PASS"'; down
setup; win; python3 -I -c 'import sqlite3,sys; c=sqlite3.connect(sys.argv[1]); c.execute("DELETE FROM t"); c.commit()' "$H/lilith-os/data/lilith.db"; g w5; check 'row lost' 'last "^W5 FAIL"'; check 'names the table' 'last "UNEXPECTED table:lilith-os/data/lilith.db:t"'; down
setup; win; echo 99 > "$S/gwpid"; g w5; check 'gateway restarted by someone' 'last "^W5 FAIL"'; down
setup; win; echo 'y: 2' > "$H/config.yaml"; g w5; check 'settings changed' 'last "^W5 FAIL"'; down
setup; win; echo changed >> "$H/memories/USER.md"; g w5; check 'USER.md changed' 'last "^W5 FAIL"'; down
setup; win; echo bad.service > "$S/failed"; g w5; check 'new failed unit' 'last "^W5 FAIL"'; down
setup; win; sed -n 's/^LILITH_OS_READ_TOKEN=//p' "$R/etc/lilith-os-api/auth.env" >> "$S/api.log"; g w5; check 'token in the journal' 'last "^W5 FAIL"'; down

setup; win; rm -f "$S/api.log"; printf '#!/bin/bash
exit 1
' > "$BIN/journalctl"; g w5; check 'unreadable journal is not a pass' 'last "^W5 FAIL"'; down

echo "== a table that moves on its own"
setup; g w0 p0; python3 -I -c 'import sqlite3,sys; c=sqlite3.connect(sys.argv[1]); c.execute("INSERT INTO t VALUES (2)"); c.commit()' "$H/state.db"; g w0 pre; g w1; fakedeploy; g w2; g w3; g w4
python3 -I -c 'import sqlite3,sys; c=sqlite3.connect(sys.argv[1]); c.execute("INSERT INTO t VALUES (3)"); c.commit()' "$H/state.db"; g w5; check 'growth in a moving table is allowed' 'last "^W5 PASS"'; check 'and reported' 'last "MOVED table:state.db:t"'; down

echo "== staging"
setup; mkdir -p "$R/tmp"; for f in guest_c1.sh live_compare.py rehearsal_compare.py; do cp "$SRC/$f" "$R/tmp/c1-$f"; done; cp "$SRC/stage_c1.sh" "$R/tmp/c1-stage_c1.sh"; rm -rf "$R/var/tmp/c1"
A=$(sha256sum "$SRC/guest_c1.sh" | cut -c1-64); B=$(sha256sum "$SRC/live_compare.py" | cut -c1-64); C=$(sha256sum "$SRC/rehearsal_compare.py" | cut -c1-64)
bash "$R/tmp/c1-stage_c1.sh" "$A" "$B" bad > "$S/last" 2>&1; check 'a wrong digest places nothing' 'last STAGE_FAILED && [ ! -e $R/var/tmp/c1 ]'
bash "$R/tmp/c1-stage_c1.sh" "$A" "$B" "$C" > "$S/last" 2>&1; check 'digests match, files placed' 'last "^STAGED" && [ -f $R/var/tmp/c1/guest_c1.sh ] && [ -f $R/var/tmp/c1/rehearsal_compare.py ]'
check 'temporary copies removed' '[ -z "$(ls $R/tmp)" ]'; down

echo "== wrong host"
setup; printf '#!/bin/bash\necho lilith-dev-01\n' > "$BIN/hostname"; C1_ROOT= bash "$R/var/tmp/c1/guest_c1.sh" w0 p0 > "$S/last" 2>&1; check 'refused on DEV' 'last WRONG_HOST'; down

echo "SIM pass=$PASS fail=$BAD"
[ "$BAD" = 0 ]
