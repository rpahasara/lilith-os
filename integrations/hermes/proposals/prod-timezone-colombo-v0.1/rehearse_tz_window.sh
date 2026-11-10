#!/usr/bin/env bash
# End-to-end rehearsal of tz_window.sh. TEST_ONLY. Root on a disposable Linux machine (never lilith-*):
#   sudo bash rehearse_tz_window.sh <proposal-dir> <hermes-release.tgz>
# The tgz is DEV's Hermes 0.20.5 release (standalone python, venv, src) at its /opt paths; its timezone and scheduler
# sources are byte-identical to PROD's. The script re-executes itself in private mount AND hostname namespaces with the
# hostname lilith-01, overlays on /etc /home /root /opt, a fresh /run, and a systemctl stand-in bind-mounted over
# /usr/bin/systemctl. A real `lilith` user owns ~/.hermes exactly as on PROD (0700 home, 0600 config and jobs). The
# stand-in gateway bridges config.yaml's timezone as run.py does, logs platform connections like gateway.run, and runs
# Hermes' real scheduler loop (get_due_jobs/mark_job_run; nothing is executed or delivered). Prints PASS/FAIL per case.
set -Eeuo pipefail
PROP=$(readlink -f "${1:?proposal dir}"); TGZ=$(readlink -f "${2:?hermes tgz}")
if [[ -z ${TZREH_INNER:-} ]]; then
  [[ $(id -u) -eq 0 ]] || { echo "run as root"; exit 2; }
  [[ $(hostname) != lilith-* ]] || { echo "refused on $(hostname)"; exit 2; }
  exec env TZREH_INNER=1 unshare -m -u --propagation private bash "$0" "$PROP" "$TGZ"
fi
hostname lilith-01
W=$(mktemp -d /tmp/tzreh.XXXXXX)
for d in etc home root opt; do mkdir -p "$W/ov/$d/u" "$W/ov/$d/w"; mount -t overlay overlay -o "lowerdir=/$d,upperdir=$W/ov/$d/u,workdir=$W/ov/$d/w" "/$d"; done
mount -t tmpfs -o mode=0755 tmpfs /run
# PROD's host clock is Etc/UTC; with no Hermes timezone, Hermes falls back to the host zone, so the sandbox must match.
ln -sfn /usr/share/zoneinfo/Etc/UTC /etc/localtime; echo Etc/UTC > /etc/timezone
[[ $(date +%Z) == UTC ]] || { echo "SETUP_FAIL host zone"; exit 2; }
chown root:root /root; chmod 0700 /root          # Ubuntu's default, as on PROD (checked read-only there)
FAILS=0; OUT=; RC=0
pass() { echo "PASS $*"; }; fail() { echo "FAIL $*"; FAILS=$((FAILS + 1)); }
check() { if eval "$2"; then pass "$1"; else fail "$1"; echo "$OUT" | tail -8 | sed 's/^/    > /'; fi; }
run() { set +e; OUT=$("$@" 2>&1); RC=$?; set -e; }

# --- a PROD-shaped host -----------------------------------------------------------------------------------------------
id lilith >/dev/null 2>&1 || useradd --create-home --home-dir /home/lilith --shell /bin/bash lilith
install -d -o lilith -g lilith -m 0750 /home/lilith
tar -C / -xzf "$TGZ"
E1=/opt/hermes-gateway-dev/releases/f293e72-f9c2-cog1-wm1-g1-r1-w1-m1-p1-e1
H=/home/lilith/.hermes; S=$H/hermes-agent; PY=$S/venv/bin/python
install -d -o lilith -g lilith -m 0700 "$H" "$H/logs" "$H/cron"
install -d -o root -g root -m 0755 "$S"
for e in "$E1"/src/*; do ln -s "$e" "$S/$(basename "$e")"; done
ln -s "$E1/venv" "$S/venv"
"$PY" -I -c "import sys; sys.path.insert(0, '$S'); import cron.jobs, hermes_time, agent.system_prompt; print('hermes imports ok')"
cat > "$W/config.yaml" <<'YAML'
model:
  default: TEST_ONLY-model
  provider: custom
compression:
  enabled: true
platform_toolsets:
  telegram: [TEST_ONLY]
  discord: [TEST_ONLY]
display:
  busy_steer_ack_enabled: false
_config_version: 7
YAML
install -o lilith -g lilith -m 0600 "$W/config.yaml" "$H/config.yaml"
PRE=$(sha256sum < "$H/config.yaml" | cut -c1-64)
runuser -u lilith -- env -i HOME=/home/lilith HERMES_HOME=$H "$PY" -I - "$S" <<'PY'
import json, os, sys
sys.path.insert(0, sys.argv[1])
import cron.jobs as J
want = {"lilith-nightly-memory-review": ("e161234245f3", "30 16 * * *"), "lilith-memory-proposal-snapshot": ("f56407e4cef8", "*/10 * * * *"),
        "lilith-commitment-sync": ("5365cfb456d4", "* * * * *")}
made = {J.create_job(prompt="TEST_ONLY never executed", schedule=e, name=n, deliver="local")["id"]: i for n, (i, e) in want.items()}
once = J.create_job(prompt="TEST_ONLY", schedule="30m", name="Drink water reminder", repeat=1, deliver="local")["id"]
p = os.path.join(os.environ["HERMES_HOME"], "cron", "jobs.json")
d = json.load(open(p))
for j in d["jobs"]:
    if j["id"] in made:
        j["id"] = made[j["id"]]
    elif j["id"] == once:
        j.update(id="7e481025f885", enabled=False, state="completed", next_run_at=None, last_run_at=j["schedule"]["run_at"], last_status="ok")
json.dump(d, open(p, "w"), indent=2)
print("jobs", [j["id"] for j in d["jobs"]])
PY
chmod 0600 "$H/cron/jobs.json"

# --- the stand-in gateway and systemctl ---------------------------------------------------------------------------------
install -d -m 0755 /opt/tzsim /run/tzsim
cat > /opt/tzsim/fakegw.py <<'PY'
import datetime as dt, os, sys, time
H = os.environ["HERMES_HOME"]; sys.path.insert(0, H + "/hermes-agent")
import yaml
tz = (yaml.safe_load(open(H + "/config.yaml")) or {}).get("timezone")
if tz:
    os.environ["HERMES_TIMEZONE"] = tz.strip()            # as run.py bridges config.yaml -> env (in-process)
FLAG = lambda n: os.path.exists("/run/tzsim/" + n)          # test switches, set by the rehearsal
if tz and FLAG("crash_if_zone"):
    sys.exit(1)
import cron.jobs as J
log = open(H + "/logs/gateway.log", "a")
def L(m):
    log.write(dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d %H:%M:%S,%f")[:23] + " INFO gateway.run: " + m + "\n"); log.flush()
time.sleep(1)
if not (tz and FLAG("no_platforms_if_zone")) and not FLAG("no_platforms"):
    for p in ("telegram", "discord", "lilith_os"):
        L(f"✓ {p} connected (profile: default)")
    L("Gateway running with 3 platform(s)")
while True:
    for j in J.get_due_jobs():
        J.mark_job_run(j["id"], True)
    time.sleep(2)
PY
cat > /opt/tzsim/systemctl <<'SH'
#!/bin/bash
D=/run/tzsim; U=; V=0; PROPS=(); CMD=$1; shift
while [ $# -gt 0 ]; do case $1 in -p) PROPS+=("$2"); shift 2;; --value) V=1; shift;; *) U=${1%.service}; shift;; esac; done
alive() { P0=$(cat $D/gw.pid 2>/dev/null); [ -n "$P0" ] && [ "$P0" -gt 0 ] 2>/dev/null && kill -0 "$P0" 2>/dev/null; }   # never pid 0
case "$CMD $U" in
  "show hermes-gateway")
    if alive; then A=active; Sb=running; P=$(cat $D/gw.pid); elif [ -e $D/gw.started ]; then A=failed; Sb=failed; P=0; else A=inactive; Sb=dead; P=0; fi
    for p in "${PROPS[@]}"; do case $p in ActiveState) x=$A;; SubState) x=$Sb;; MainPID) x=$P;; NRestarts) x=0;; ActiveEnterTimestamp) x=$(cat $D/gw.enter 2>/dev/null);; *) x=;; esac
      if [ $V = 1 ]; then echo "$x"; else echo "$p=$x"; fi; done ;;
  "start hermes-gateway")
    alive && exit 0
    date -u '+%a %Y-%m-%d %H:%M:%S UTC' > $D/gw.enter; touch $D/gw.started
    setsid runuser -u lilith -- env -i HOME=/home/lilith HERMES_HOME=/home/lilith/.hermes PATH=/usr/bin:/bin \
      ${SIM_GW_CRASH_IF_ZONE:+SIM_GW_CRASH_IF_ZONE=1} ${SIM_GW_NO_PLATFORMS_IF_ZONE:+SIM_GW_NO_PLATFORMS_IF_ZONE=1} ${SIM_GW_NO_PLATFORMS:+SIM_GW_NO_PLATFORMS=1} \
      /home/lilith/.hermes/hermes-agent/venv/bin/python -I /opt/tzsim/fakegw.py >/dev/null 2>&1 < /dev/null &
    sleep 1; P=$(pgrep -u lilith -f "^/home/lilith/.hermes/hermes-agent/venv/bin/python -I /opt/tzsim/fakegw.py" | head -1); echo "${P:-0}" > $D/gw.pid; exit 0 ;;
  "stop hermes-gateway")
    pkill -u lilith -f fakegw.py 2>/dev/null; for i in $(seq 50); do pgrep -u lilith -f fakegw.py >/dev/null || break; sleep 0.1; done
    : > $D/gw.pid; rm -f $D/gw.started; exit 0 ;;
  "is-active lilith-os-api") [ -e $D/api.down ] && { echo inactive; exit 3; }; echo active ;;
  *) echo "tzsim systemctl refused: $CMD $U" >&2; exit 1 ;;
esac
SH
chmod 0755 /opt/tzsim/systemctl; mount --bind /opt/tzsim/systemctl /usr/bin/systemctl
SC=/usr/bin/systemctl

# --- helpers -------------------------------------------------------------------------------------------------------------
TW="$PROP/tz_window.sh"
export TZ_SIM=1 TZ_SIM_CONFIG_SHA=$PRE
cfgsha() { sha256sum < "$H/config.yaml" | cut -c1-64; }
jobsinfo() { runuser -u lilith -- python3 -I -c '
import json, datetime as dt
d = {j["id"]: j for j in json.load(open("/home/lilith/.hermes/cron/jobs.json"))["jobs"]}
r = d["e161234245f3"]; n = dt.datetime.fromisoformat(r["next_run_at"])
c = d["5365cfb456d4"]["next_run_at"]
print(r["schedule"]["expr"], n.utcoffset(), n.astimezone(dt.timezone.utc).strftime("%H:%M"), d["f56407e4cef8"]["schedule"]["expr"], d["5365cfb456d4"]["schedule"]["expr"],
      "sync_offset", dt.datetime.fromisoformat(c).utcoffset(), "once_enabled", d["7e481025f885"]["enabled"], len(d))'; }
UTC_STATE="30 16 * * * 0:00:00 16:30 */10 * * * * * * * * * sync_offset 0:00:00 once_enabled False 4"
COL_STATE="0 22 * * * 5:30:00 16:30 */10 * * * * * * * * * sync_offset 5:30:00 once_enabled False 4"
gw_running() { [[ $($SC show hermes-gateway -p ActiveState --value) == active ]]; }
synced() {   # the live scheduler really ran commitment sync in the last 150 s, writing times with offset $1
  runuser -u lilith -- python3 -I -c '
import json, sys, datetime as dt
c = {j["id"]: j for j in json.load(open("/home/lilith/.hermes/cron/jobs.json"))["jobs"]}["5365cfb456d4"]
ok = c.get("last_run_at") and (dt.datetime.now(dt.timezone.utc) - dt.datetime.fromisoformat(c["last_run_at"])).total_seconds() < 150      and str(dt.datetime.fromisoformat(c["next_run_at"]).utcoffset()) == sys.argv[1]
sys.exit(0 if ok else 1)' "$1"; }
wait_sync() { for i in $(seq 360); do synced "$1" && return 0; sleep 1; done; return 1; }
baseline() {   # back to the pristine UTC state with a healthy gateway (used after an escalation)
  $SC stop hermes-gateway
  install -o lilith -g lilith -m 0600 "$W/config.yaml" "$H/config.yaml"
  install -o lilith -g lilith -m 0600 "$W/jobs.baseline" "$H/cron/jobs.json"
  $SC start hermes-gateway; wait_sync 0:00:00; sleep 3
}
utc_ok() { [[ $(cfgsha) == "$PRE" && $(jobsinfo) == "$UTC_STATE" ]] && gw_running; }
bkdir() { ls -1d /root/tz-colombo-* 2>/dev/null | tail -1; }

$SC start hermes-gateway; wait_sync 0:00:00 || { echo "SETUP_FAIL scheduler"; jobsinfo; pgrep -af fakegw; ls -la /run/tzsim; cat /run/tzsim/gw.pid; tail -5 $H/logs/gateway.log;
  runuser -u lilith -- env -i HOME=/home/lilith HERMES_HOME=$H PATH=/usr/bin:/bin timeout 8 $PY -I /opt/tzsim/fakegw.py; echo "fakegw rc=$?"; exit 2; }; sleep 3
cp -p "$H/cron/jobs.json" "$W/jobs.baseline"
check "setup: PROD-shaped host, lilith-owned ~/.hermes, gateway running, scheduler ticking in UTC" \
  '[[ $(stat -c "%U %a" $H) == "lilith 700" && $(stat -c "%U %a" $H/config.yaml) == "lilith 600" && $(stat -c "%U %a" $H/cron/jobs.json) == "lilith 600" ]] && utc_ok'

# --- permissions ---------------------------------------------------------------------------------------------------------
install -d -o root -g root -m 0700 /root/tz-colombo-permtest
run runuser -u lilith -- touch /root/tz-colombo-permtest/x
check "permission: lilith cannot write a root 0700 backup dir (the old design's failure)" '[[ $RC -ne 0 && $OUT == *"ermission denied"* ]]'
rmdir /root/tz-colombo-permtest
install -d -m 0755 /opt/tzsim/prop; install -m 0644 "$PROP"/tz_window.sh "$PROP"/tz_ops.py /opt/tzsim/prop/
run runuser -u lilith -- bash /opt/tzsim/prop/tz_window.sh precheck
check "permission: the script refuses to run as lilith" '[[ $RC -ne 0 && $OUT == *"not root"* ]] && utc_ok'

# --- precheck ------------------------------------------------------------------------------------------------------------
run bash "$TW" precheck; check "precheck PASS on the PROD-shaped host" '[[ $RC -eq 0 && $OUT == *TZ_PRECHECK_PASS* ]]'
for c in 16:20 02:10; do run env TZ_SIM_CLOCK=$c bash "$TW" precheck; check "precheck refuses at $c (blackout)" '[[ $RC -ne 0 && $OUT == *blackout* ]]'; done
echo "# TEST_ONLY" >> "$H/config.yaml"; run bash "$TW" precheck
check "precheck refuses a config.yaml that is not the inventoried one" '[[ $RC -ne 0 && $OUT == *"not the inventoried"* ]]'
install -o lilith -g lilith -m 0600 "$W/config.yaml" "$H/config.yaml"
runuser -u lilith -- env -i HOME=/home/lilith HERMES_HOME=$H "$PY" -I -c "import sys; sys.path.insert(0,'$S'); import cron.jobs as J; J.create_job(prompt='TEST_ONLY', schedule='2026-12-01T20:00:00+05:30', name='TEST_ONLY reminder', deliver='local')"
run bash "$TW" precheck; check "precheck refuses an extra enabled reminder (no silent reinterpretation)" '[[ $RC -ne 0 && $OUT == *"differs from the inventory"* ]]'
runuser -u lilith -- env -i HOME=/home/lilith HERMES_HOME=$H "$PY" -I -c "import sys; sys.path.insert(0,'$S'); import cron.jobs as J; [J.remove_job(j['id']) for j in J.load_jobs() if j['name']=='TEST_ONLY reminder']"
touch /run/tzsim/api.down; run bash "$TW" precheck; rm -f /run/tzsim/api.down
check "precheck refuses with the Core API down" '[[ $RC -ne 0 && $OUT == *"Core API"* ]]'
$SC stop hermes-gateway; run bash "$TW" precheck; $SC start hermes-gateway; wait_sync 0:00:00; sleep 3
check "precheck refuses with the gateway down" '[[ $RC -ne 0 && $OUT == *"gateway not running"* ]] && utc_ok'

# --- change: an injected failure at every boundary ---------------------------------------------------------------------
P0=$($SC show hermes-gateway -p MainPID --value)
run env TZ_SIM_FAIL_AT=prepare bash "$TW" change
check "change fails while preparing: nothing changed, gateway never stopped (same pid)" '[[ $RC -eq 1 && $OUT == *"nothing changed"* && $($SC show hermes-gateway -p MainPID --value) == "$P0" ]] && utc_ok'
for at in after_stop backup_jobs; do
  run env TZ_SIM_FAIL_AT=$at bash "$TW" change
  check "change fails at $at: nothing modified, gateway restarted and proven in UTC" '[[ $RC -eq 1 && $OUT == *"TZ_FAIL_RECOVERED"* && $OUT == *"nothing was changed"* && $OUT == *"gateway proven"* ]] && utc_ok'
done
for at in after_backup after_config jobs_apply after_jobs; do
  run env TZ_SIM_FAIL_AT=$at bash "$TW" change
  check "change fails at $at: exact restore verified, gateway proven in UTC" '[[ $RC -eq 1 && $OUT == *"TZ_FAIL_RECOVERED"* && $OUT == *"checksums verified"* && $OUT == *"gateway proven"* ]] && utc_ok'
done
run env TZ_SIM_FAIL_AT=start bash "$TW" change
check "change: start step fails -> documented rollback, proven in UTC" '[[ $RC -eq 1 && $OUT == *"TZ_FAIL_ROLLED_BACK"* ]] && utc_ok'
touch /run/tzsim/crash_if_zone; run bash "$TW" change; rm -f /run/tzsim/crash_if_zone
check "change: gateway dies on the new config (systemctl accepted the start) -> rollback, proven in UTC" '[[ $RC -eq 1 && ( $OUT == *"not active/running"* || $OUT == *"not stable"* ) && $OUT != *"no platform evidence"* && $OUT == *"TZ_FAIL_ROLLED_BACK"* ]] && utc_ok'
touch /run/tzsim/no_platforms_if_zone; run bash "$TW" change; rm -f /run/tzsim/no_platforms_if_zone
check "change: running but no platform evidence from this start -> rollback, proven in UTC" '[[ $RC -eq 1 && $OUT == *"no platform evidence"* && $OUT == *"TZ_FAIL_ROLLED_BACK"* ]] && utc_ok'
run env TZ_SIM_FAIL_AT=after_config TZ_SIM_CORRUPT_BACKUP=1 bash "$TW" change
check "change: backup cannot be verified during recovery -> TZ_ESCALATE, exit 3, gateway left STOPPED" '[[ $RC -eq 3 && $OUT == *"TZ_ESCALATE"* ]] && ! gw_running'
baseline; check "  (sandbox reset to baseline)" 'utc_ok'
check "backups: every backup dir is root 0700 with root 0600 files, lilith cannot read them" \
  '[[ -z $(find /root -maxdepth 1 -name "tz-colombo-*" ! -perm 0700) && -z $(find /root/tz-colombo-* -type f ! -user root) && -z $(find /root/tz-colombo-* -type f -perm /0077) ]] && ! runuser -u lilith -- cat "$(bkdir)/config.yaml" >/dev/null 2>&1'
check "no ops dirs left in /run" '[[ -z $(ls -d /run/tz-colombo-ops.* 2>/dev/null) ]]'

# --- success, restart, verify ------------------------------------------------------------------------------------------
run bash "$TW" change; BK=$(bkdir)
check "change succeeds: TZ_CHANGED with the gateway proven in the new zone" '[[ $RC -eq 0 && $OUT == *"TZ_CHANGED backup="* && $OUT == *"gateway proven"* ]]'
check "  config.yaml = original + timezone line, lilith 0600" '[[ $(cat $H/config.yaml) == "$(cat $W/config.yaml)"$'"'"'\ntimezone: Asia/Colombo'"'"' && $(stat -c "%U %a" $H/config.yaml) == "lilith 600" ]]'
check "  review 0 22 * * * at +05:30 = 16:30Z; snapshot/sync unchanged; live sync writes +05:30; reminder untouched" '[[ $(jobsinfo) == "$COL_STATE" ]]'
run bash "$TW" verify h60 colombo; check "verify colombo PASS, exit 0" '[[ $RC -eq 0 && $OUT == *"TZ_VERIFY h60 colombo PASS"* ]]'
run bash "$TW" verify wrong utc; check "verify utc on the changed host FAILs with a nonzero exit" '[[ $RC -ne 0 && $OUT == *"TZ_VERIFY wrong utc FAIL"* ]]'
$SC stop hermes-gateway; run bash "$TW" verify down colombo
check "verify with the gateway down: V1 FAIL, nonzero" '[[ $RC -ne 0 && $OUT == *"FAIL V1"* ]]'
touch /run/tzsim/no_platforms; $SC start hermes-gateway; sleep 5; run bash "$TW" verify noplat colombo; rm -f /run/tzsim/no_platforms
check "verify after a start that logged no platforms: V6 FAIL (older starts' lines do not count), nonzero" '[[ $RC -ne 0 && $OUT == *"FAIL V6"* ]]'
$SC stop hermes-gateway; $SC start hermes-gateway; wait_sync 5:30:00; sleep 3
run bash "$TW" verify restart colombo; check "after a plain restart the zone and the 16:30Z review persist (verify PASS)" '[[ $RC -eq 0 && $(jobsinfo) == "$COL_STATE" ]]'
run bash "$TW" change; check "a second change refuses (config is no longer the inventoried one); nothing changed" '[[ $RC -eq 1 && $OUT == *"nothing changed"* && $(jobsinfo) == "$COL_STATE" ]]'

# --- rollback --------------------------------------------------------------------------------------------------------------
run env TZ_SIM_CLOCK=16:10 bash "$TW" rollback "$BK"; check "rollback refuses inside the blackout; nothing changed" '[[ $RC -eq 1 && $OUT == *blackout* && $(jobsinfo) == "$COL_STATE" ]] && gw_running'
cp -p "$H/config.yaml" "$W/config.colombo"
run env TZ_SIM_CORRUPT_BACKUP=1 bash "$TW" rollback "$BK"
check "rollback: restored config cannot be verified -> TZ_ESCALATE, exit 3, gateway left STOPPED" '[[ $RC -eq 3 && $OUT == *TZ_ESCALATE* ]] && ! gw_running'
install -o lilith -g lilith -m 0600 "$W/config.colombo" "$H/config.yaml"; (cd "$BK" && sed -i '/TEST_ONLY corruption/d' config.yaml && sha256sum -c --quiet SHA256SUMS)
$SC start hermes-gateway; wait_sync 5:30:00; sleep 3
run env TZ_SIM_FAIL_AT=jobs_revert bash "$TW" rollback "$BK"
check "rollback with jobs-revert failing: exact jobs.json fallback, proven in UTC, TZ_ROLLED_BACK" '[[ $RC -eq 0 && $OUT == *"restoring jobs.json exactly"* && $OUT == *TZ_ROLLED_BACK* ]] && utc_ok'
run bash "$TW" verify after-rollback utc; check "verify utc after rollback PASS" '[[ $RC -eq 0 ]]'
run bash "$TW" change; BK2=$(bkdir); check "change again succeeds" '[[ $RC -eq 0 && $(jobsinfo) == "$COL_STATE" ]]'
run bash "$TW" rollback "$BK2"
check "rollback (documented path, jobs-revert through Hermes): config byte-identical to the original, review 30 16 UTC = 16:30Z" '[[ $RC -eq 0 && $OUT == *JOBS_REVERT_OK* && $OUT == *TZ_ROLLED_BACK* ]] && utc_ok'
run bash "$TW" verify final utc; check "final verify utc PASS" '[[ $RC -eq 0 ]]'

$SC stop hermes-gateway
echo "REHEARSAL_RESULT $([[ $FAILS -eq 0 ]] && echo PASS || echo "FAIL ($FAILS)")"
exit $FAILS
