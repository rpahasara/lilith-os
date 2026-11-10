#!/usr/bin/env bash
# PROD Hermes Asia/Colombo migration (proposal; run only with the owner's explicit authorization). Root on lilith-01.
#   sudo bash tz_window.sh precheck                 read-only: every precondition, blackout windows, the planned instant
#   sudo bash tz_window.sh change                   prepare (gateway running) -> stop -> config + review -> start + proof
#   sudo bash tz_window.sh verify LABEL colombo|utc read-only post-checks V1-V7; exit 0 only if every check passes
#   sudo bash tz_window.sh rollback BACKUP_DIR      stop -> exact config restore -> review back to UTC -> start + proof
# Writes: /root/tz-colombo-<ts>/ (root 0700 backups, written by root only), ~/.hermes/config.yaml (one appended line,
# installed by root as lilith:lilith 0600) and the review job's schedule in ~/.hermes/cron/jobs.json (Hermes' own
# update_job, as lilith). Nothing else.
# Exit codes: 0 done | 1 refused or failed, and the previous state is restored, verified and running (or nothing was
# changed) | 3 TZ_ESCALATE: files could not be verified; the gateway is left STOPPED for a human.
set -Euo pipefail
umask 077
MODE=${1:-}
HERE=$(cd "$(dirname "$0")" && pwd)
H=/home/lilith/.hermes; S=$H/hermes-agent; PY=$S/venv/bin/python
CFG=$H/config.yaml; JOBS=$H/cron/jobs.json; GWLOG=$H/logs/gateway.log
CONFIG_PRE_SHA=a6f340f2221130e4d9e142195ce86b8dab9721c0a67c2ca4359950ad39ec37e7   # 2026-11-10 inventory (no timezone key)
PLATFORMS=(telegram discord lilith_os)
STABLE_S=10; START_WAIT_S=90; PLATFORM_WAIT_S=120; EVIDENCE_WAIT_S=150
declare -A SRC_SHA=(   # PROD Hermes 0.20.5 timezone-relevant sources, byte-identical to the DEV-rehearsed ones
  [hermes_time.py]=3f4ee146597bbb2dabf61ed0458b3e9c7f2dcb9dd89351652cd0fc6e8a7884c8
  [cron/jobs.py]=edf2469d61286ba7ec13ffabddfaef2a9b5e7f51b2ac08c3494eb5ea4aa7177b
  [agent/system_prompt.py]=1d1c1bfbfc3752576f8523bfc5029b8ab3a005a195b2abd10c85ccc9cd20164d
  [gateway/message_timestamps.py]=daa620ef95760d35154d8cf6f6ec6774ea1dbf6b390d101886359d57757fa222
)
now() { date -u +%Y-%m-%dT%H:%M:%S.%3NZ; }
say() { echo "$(now) $*"; }
refuse() { echo "TZ_FAIL $* (nothing changed)" >&2; exit 1; }
escalate() { echo "TZ_ESCALATE $* - gateway left STOPPED; do not start it until a human has checked the files" >&2; exit 3; }
sha() { sha256sum "$1" | cut -d' ' -f1; }

# Offline rehearsal only (tests/rehearse_tz_window.sh). Honoured only inside private mount AND hostname namespaces with
# /home and /root on overlays; anywhere else it is refused before anything runs.
SIM=0
if [[ -n ${TZ_SIM:-} ]]; then
  [[ ${TZ_SIM} == 1 && $(readlink /proc/1/ns/mnt) != "$(readlink /proc/self/ns/mnt)" \
     && $(readlink /proc/1/ns/uts) != "$(readlink /proc/self/ns/uts)" \
     && $(stat -f -c %T /home) == overlayfs && $(stat -f -c %T /root) == overlayfs ]] || refuse "TZ_SIM outside a sandbox"
  SIM=1; CONFIG_PRE_SHA=${TZ_SIM_CONFIG_SHA:?}; STABLE_S=2; PLATFORM_WAIT_S=30; EVIDENCE_WAIT_S=75
fi
inject() { [[ $SIM == 1 && ${TZ_SIM_FAIL_AT:-} == "$1" ]] && { echo "INJECTED_FAILURE at $1" >&2; return 1; }; return 0; }

# tz_ops.py runs as lilith from a fresh root-owned, read-only copy that lilith can read but not change.
OPSDIR=
setup_ops() {
  OPSDIR=$(mktemp -d /run/tz-colombo-ops.XXXXXX) || refuse "ops dir"
  chmod 0755 "$OPSDIR"; install -o root -g root -m 0644 "$HERE/tz_ops.py" "$OPSDIR/tz_ops.py" || refuse "ops copy"
}
cleanup_ops() { [[ -n $OPSDIR && -f $OPSDIR/tz_ops.py ]] && unlink "$OPSDIR/tz_ops.py"; [[ -n $OPSDIR ]] && rmdir "$OPSDIR" 2>/dev/null; return 0; }
trap cleanup_ops EXIT
ops() {   # [VAR=value ...] command [args]; stdin is passed through
  local envs=(); while [[ ${1:-} == *=* ]]; do envs+=("$1"); shift; done
  runuser -u lilith -- env -i HOME=/home/lilith HERMES_HOME=$H PATH=/usr/bin:/bin "${envs[@]}" "$PY" -I "$OPSDIR/tz_ops.py" "$@"
}
gwp() { systemctl show hermes-gateway -p "$1" --value 2>/dev/null; }
gw() { systemctl show hermes-gateway -p ActiveState -p SubState -p MainPID -p NRestarts | LC_ALL=C sort | paste -sd' '; }

blackout() {   # refuse near the review (16:30Z) and the morning brief (02:30Z)
  local hm=$(date -u +%H:%M); [[ $SIM == 1 && -n ${TZ_SIM_CLOCK:-} ]] && hm=$TZ_SIM_CLOCK
  local m=$((10#${hm%:*} * 60 + 10#${hm#*:}))
  (( m >= 16 * 60 && m < 17 * 60 )) && refuse "inside the 16:00-17:00Z review blackout ($hm)"
  (( m >= 2 * 60 && m < 3 * 60 )) && refuse "inside the 02:00-03:00Z morning-brief blackout ($hm)"
  return 0
}

precheck() {   # read-only
  [[ $(id -u) -eq 0 ]] || refuse "not root"
  [[ $(hostname -s) == lilith-01 ]] || refuse "wrong host $(hostname -s)"
  blackout; echo "PASS outside blackout windows"
  local f; for f in "${!SRC_SHA[@]}"; do [[ $(sha "$S/$f") == "${SRC_SHA[$f]}" ]] || refuse "Hermes source $f changed"; done
  echo "PASS Hermes timezone sources = the DEV-rehearsed bytes"
  [[ $(sha "$CFG") == "$CONFIG_PRE_SHA" ]] || refuse "config.yaml is not the inventoried one (re-plan)"
  [[ $(stat -c '%U:%G %a' "$CFG") == "lilith:lilith 600" ]] || refuse "config.yaml owner/mode"
  [[ $(ops config-check) == '{"timezone": null}' ]] || refuse "config.yaml already has a timezone"
  echo "PASS config.yaml is the inventoried one, no timezone key"
  [[ $(gw) == *"ActiveState=active"*"SubState=running"* ]] || refuse "gateway not running"
  [[ -z $(tr '\0' '\n' < "/proc/$(gwp MainPID)/environ" | grep -E '^(HERMES_TIMEZONE|TZ)=') ]] || refuse "gateway started with a zone in its environment"
  echo "PASS gateway $(gw)"
  local inv; inv=$(ops jobs-inspect 2>&1) || { echo "$inv" | tail -2 >&2; refuse "job set differs from the inventory (re-plan)"; }
  echo "PASS job set = the three inventoried recurring jobs, nothing else enabled, all timestamps zone-aware"
  local plan; plan=$(ops jobs-plan) || refuse "planned review instant"
  [[ $plan == *'"same_instant": true'* ]] || refuse "planned review instant"; echo "PASS plan $plan"
  local ev; ev=$(ops jobs-evidence "$(date -u -d '-180 sec' +%Y-%m-%dT%H:%M:%S+00:00)" utc) || refuse "scheduler not ticking in UTC ($ev)"
  echo "PASS live scheduler ticking in UTC $ev"
  [[ $(systemctl is-active lilith-os-api) == active ]] || refuse "Core API not active"; echo "PASS Core API active"
  (( $(df -Pm "$H" | awk 'NR==2{print $4}') > 500 )) || refuse "disk"; echo "PASS disk"
  [[ -w /root && $(stat -c '%U %a' /root) == "root 700" ]] || refuse "/root not root 0700"
  echo "TZ_PRECHECK_PASS"
}

wait_stopped() { local i; for i in $(seq 60); do [[ $(gwp MainPID) == 0 ]] && return 0; sleep 1; done; return 1; }

start_and_prove() {   # $1 colombo|utc. Success only with a running, stable gateway that logged this start's platforms
  local zone=$1 t0 t0_log pid r0 i
  t0=$(date -u +%Y-%m-%dT%H:%M:%S+00:00); t0_log=$(date -u '+%Y-%m-%d %H:%M:%S'); r0=$(gwp NRestarts)
  say "start hermes-gateway"
  systemctl start hermes-gateway || { echo "  start request refused" >&2; return 1; }
  for i in $(seq $START_WAIT_S); do [[ $(gw) == *"ActiveState=active"*"SubState=running"* ]] && break; sleep 1; done
  [[ $(gw) == *"ActiveState=active"*"SubState=running"* ]] || { echo "  not active/running: $(gw)" >&2; return 1; }
  pid=$(gwp MainPID); sleep $STABLE_S
  [[ $(gwp MainPID) == "$pid" && $(gwp NRestarts) == "$r0" && $(gw) == *"ActiveState=active"* ]] \
    || { echo "  not stable: $(gw) (pid was $pid)" >&2; return 1; }
  local seen=0; for i in $(seq $PLATFORM_WAIT_S); do
    local since; since=$(awk -v t="$t0_log" 'substr($0,1,19) >= t' "$GWLOG" 2>/dev/null)
    seen=1; for p in "${PLATFORMS[@]}"; do grep -q "✓ $p connected" <<< "$since" || seen=0; done
    grep -q "Gateway running with ${#PLATFORMS[@]} platform(s)" <<< "$since" || seen=0
    [[ $seen == 1 ]] && break; sleep 1
  done
  [[ $seen == 1 ]] || { echo "  no platform evidence from this start (since $t0_log)" >&2; return 1; }
  local ev; for i in $(seq $EVIDENCE_WAIT_S); do ev=$(ops jobs-evidence "$t0" "$zone") && break; sleep 1; done
  ops jobs-evidence "$t0" "$zone" > /dev/null || { echo "  live scheduler shows no $zone times since start: $ev" >&2; return 1; }
  [[ $(gwp MainPID) == "$pid" ]] || { echo "  restarted during proof" >&2; return 1; }
  say "gateway proven: $(gw); platforms ${PLATFORMS[*]} connected since $t0_log; scheduler $ev"
  return 0
}

restore_exact() {   # $1 backup dir; both files back, byte-identical to the checksums recorded while stopped
  local bk=$1
  [[ -f $bk/SHA256SUMS && -f $bk/config.yaml && -f $bk/jobs.json ]] || return 1
  (cd "$bk" && sha256sum -c --quiet --strict SHA256SUMS >/dev/null 2>&1) || return 1
  [[ $SIM == 1 && ${TZ_SIM_CORRUPT_BACKUP:-} == 1 ]] && echo "TEST_ONLY corruption" >> "$bk/jobs.json"
  install -o lilith -g lilith -m 0600 "$bk/config.yaml" "$CFG.tz-restore" && mv -f "$CFG.tz-restore" "$CFG" || return 1
  install -o lilith -g lilith -m 0600 "$bk/jobs.json" "$JOBS.tz-restore" && mv -f "$JOBS.tz-restore" "$JOBS" || return 1
  [[ $(sha "$CFG") == $(awk '$2=="config.yaml"{print $1}' "$bk/SHA256SUMS") \
     && $(sha "$JOBS") == $(awk '$2=="jobs.json"{print $1}' "$bk/SHA256SUMS") ]] || return 1
  return 0
}

recover_stopped() {   # gateway stopped, files possibly changed: exact restore, verify, then start on the old state
  echo "TZ_FAIL during change: $1 - restoring $BK" >&2
  wait_stopped || escalate "gateway not stopped during recovery"
  restore_exact "$BK" || escalate "backup restore could not be verified"
  echo "  restored config.yaml and jobs.json exactly (checksums verified)" >&2
  start_and_prove utc || escalate "files restored, but the gateway did not come back healthy"
  echo "TZ_FAIL_RECOVERED $1 (previous configuration restored, verified and running)" >&2
  exit 1
}

rollback_files() {   # gateway stopped: exact config, review back to 30 16 UTC through Hermes; exact jobs as fallback
  local bk=$1
  [[ $(awk '$2=="config.yaml"{print $1}' "$bk/SHA256SUMS") == "$CONFIG_PRE_SHA" ]] || return 1
  (cd "$bk" && sha256sum -c --quiet --strict SHA256SUMS >/dev/null 2>&1) || return 1
  [[ $SIM == 1 && ${TZ_SIM_CORRUPT_BACKUP:-} == 1 ]] && echo "TEST_ONLY corruption" >> "$bk/config.yaml"
  install -o lilith -g lilith -m 0600 "$bk/config.yaml" "$CFG.tz-restore" && mv -f "$CFG.tz-restore" "$CFG" || return 1
  [[ $(sha "$CFG") == "$CONFIG_PRE_SHA" ]] || return 1
  local out
  if out=$( { inject jobs_revert && ops jobs-revert; } 2>&1) && grep -q '^JOBS_REVERT_OK' <<< "$out"; then
    echo "$out" | tail -2
  else
    echo "  jobs-revert failed ($(tail -1 <<< "$out")); restoring jobs.json exactly from the backup" >&2
    install -o lilith -g lilith -m 0600 "$bk/jobs.json" "$JOBS.tz-restore" && mv -f "$JOBS.tz-restore" "$JOBS" || return 1
    [[ $(sha "$JOBS") == $(awk '$2=="jobs.json"{print $1}' "$bk/SHA256SUMS") ]] || return 1
  fi
  return 0
}

rollback_running() {   # after a start failure with the new configuration: the documented rollback, automatically
  echo "TZ_FAIL after the change: $1 - rolling back" >&2
  systemctl stop hermes-gateway; wait_stopped || escalate "gateway would not stop for rollback"
  rollback_files "$BK" || escalate "rollback files could not be verified"
  start_and_prove utc || escalate "rolled back, but the gateway did not come back healthy"
  echo "TZ_FAIL_ROLLED_BACK $1 (previous configuration restored, verified and running)" >&2
  exit 1
}

case $MODE in
  precheck)
    setup_ops; precheck ;;
  change)
    setup_ops; precheck
    # -- prepare while the gateway runs: any failure here changes nothing
    BK=/root/tz-colombo-$(date -u +%Y%m%dT%H%M%SZ)
    install -d -o root -g root -m 0700 "$BK" || refuse "backup dir"
    cp -p "$CFG" "$BK/config.yaml" && [[ $(sha "$BK/config.yaml") == "$CONFIG_PRE_SHA" ]] || refuse "config backup"
    inject prepare || refuse "injected"
    ops config-render > "$BK/config.new" || refuse "config render"
    ops config-validate < "$BK/config.new" | grep -qx CONFIG_VALID || refuse "rendered config does not validate"
    NEWSHA=$(sha "$BK/config.new"); say "prepared $BK (config.new $NEWSHA)"
    # -- stop
    say "stop hermes-gateway"
    systemctl stop hermes-gateway; wait_stopped || refuse "gateway did not stop (check it is running again)"
    J0=$(sha "$JOBS"); C0=$(sha "$CFG"); say "stopped $(gw)"
    [[ $C0 == "$CONFIG_PRE_SHA" ]] || { start_and_prove utc || escalate "config changed under us and the gateway did not restart"; refuse "config.yaml changed during preparation"; }
    # -- from here every step is checked; any failure restores exactly, verifies, and starts the old state
    unchanged_restart() { [[ $(sha "$CFG") == "$C0" && $(sha "$JOBS") == "$J0" ]] || escalate "files changed but no verified backup exists"; \
                          start_and_prove utc || escalate "nothing changed, but the gateway did not come back healthy"; \
                          echo "TZ_FAIL_RECOVERED $1 (nothing was changed; gateway running)" >&2; exit 1; }
    inject after_stop || unchanged_restart "injected after stop"
    { inject backup_jobs && cp -p "$JOBS" "$BK/jobs.json"; } || unchanged_restart "jobs.json backup failed"
    [[ $(sha "$BK/jobs.json") == "$J0" ]] || unchanged_restart "jobs.json backup does not match"
    (cd "$BK" && printf '%s  config.yaml\n%s  jobs.json\n' "$C0" "$J0" > SHA256SUMS && sha256sum -c --quiet --strict SHA256SUMS) \
      || unchanged_restart "backup checksums"
    say "backups verified: config.yaml $C0, jobs.json $J0"
    inject after_backup || recover_stopped "injected after backup"
    install -o lilith -g lilith -m 0600 "$BK/config.new" "$CFG.tz-new" && mv -f "$CFG.tz-new" "$CFG" || recover_stopped "config install"
    [[ $(sha "$CFG") == "$NEWSHA" && $(ops config-check) == '{"timezone": "Asia/Colombo"}' ]] || recover_stopped "config check"
    inject after_config || recover_stopped "injected after config"
    OUT=$( { inject jobs_apply && ops HERMES_TIMEZONE=Asia/Colombo jobs-apply; } 2>&1) && grep -q '^JOBS_APPLY_OK' <<< "$OUT" \
      || recover_stopped "jobs-apply ($(tail -1 <<< "$OUT"))"
    echo "$OUT" > "$BK/jobs-apply.out"; tail -2 <<< "$OUT"
    inject after_jobs || recover_stopped "injected after jobs"
    # -- start and prove; a failed start rolls back by the documented procedure
    { inject start && start_and_prove colombo; } || rollback_running "gateway did not start healthy on the new configuration"
    echo "TZ_CHANGED backup=$BK"
    ;;
  verify)
    LABEL=${2:-check}; ZONE=${3:-colombo}; setup_ops; fail=0
    v() { if eval "$2"; then echo "PASS $1"; else echo "FAIL $1"; fail=1; fi; }
    [[ $(hostname -s) == lilith-01 ]] || refuse "wrong host"
    v "V1 gateway active/running: $(gw)" '[[ $(gw) == *"ActiveState=active"*"SubState=running"* ]]'
    want_tz=$([[ $ZONE == colombo ]] && echo '{"timezone": "Asia/Colombo"}' || echo '{"timezone": null}')
    v "V2 config.yaml $want_tz" '[[ $(ops config-check) == "$want_tz" ]]'
    START=$(date -u -d "$(gwp ActiveEnterTimestamp)" +%Y-%m-%dT%H:%M:%S+00:00 2>/dev/null || echo 1970-01-01T00:00:00+00:00)
    EV=$(ops jobs-evidence "$START" "$ZONE"); v "V2 live scheduler writes $ZONE times since this start: $EV" '[[ $EV == *"\"ok\": true"* ]]'
    DC=$(ops datecheck); want_zone=$([[ $ZONE == colombo ]] && echo '"zone": "Asia/Colombo"' || echo '"zone": null')
    v "V3 $DC" '[[ $DC == *"$want_zone"* ]]'
    REV=$(ops jobs-inspect | "$PY" -I -c '
import json, sys, datetime as dt
r = {x["id"]: x for x in json.load(sys.stdin)}["e161234245f3"]; n = dt.datetime.fromisoformat(r["next_run_at"]); u = n.astimezone(dt.timezone.utc)
print(r["expr"], r["next_run_at"], u.isoformat(), n.utcoffset() == (dt.timedelta(hours=5, minutes=30) if sys.argv[1] == "colombo" else dt.timedelta(0)) and (u.hour, u.minute) == (16, 30))' "$ZONE")
    want_expr=$([[ $ZONE == colombo ]] && echo "0 22 * * *" || echo "30 16 * * *")
    v "V4 review $REV" '[[ $REV == "$want_expr "* && $REV == *" True" ]]'
    SNAP=$(ops jobs-inspect | "$PY" -I -c '
import json, sys, datetime as dt
j = {x["id"]: x for x in json.load(sys.stdin)}; now = dt.datetime.now(dt.timezone.utc)
s = j["f56407e4cef8"]; c = j["5365cfb456d4"]
ok = all(x["last_status"] == "ok" for x in (s, c)) and (now - dt.datetime.fromisoformat(c["last_run_at"])).total_seconds() < 150 \
     and (now - dt.datetime.fromisoformat(s["last_run_at"])).total_seconds() < 700
print("sync", c["last_run_at"], "snapshot", s["last_run_at"], ok)')
    v "V5 jobs on time: $SNAP" '[[ $SNAP == *" True" ]]'
    LOGSINCE=$(date -u -d "$(gwp ActiveEnterTimestamp)" '+%Y-%m-%d %H:%M:%S' 2>/dev/null || echo 9999)
    SINCE=$(awk -v t="$LOGSINCE" 'substr($0,1,19) >= t' "$GWLOG" 2>/dev/null)
    platforms_since() { local p; for p in "${PLATFORMS[@]}"; do grep -q "✓ $p connected" <<< "$SINCE" || return 1; done
                        grep -q "Gateway running with ${#PLATFORMS[@]} platform(s)" <<< "$SINCE"; }
    v "V6 platforms connected since this start ($LOGSINCE)" 'platforms_since'
    v "V7 Core API active" '[[ $(systemctl is-active lilith-os-api) == active ]]'
    echo "TZ_VERIFY $LABEL $ZONE $([[ $fail == 0 ]] && echo PASS || echo FAIL) $(now)"
    exit $fail
    ;;
  rollback)
    BK=${2:-}; [[ -n $BK && -f $BK/SHA256SUMS && -f $BK/config.yaml && -f $BK/jobs.json ]] || refuse "backup dir"
    [[ $(id -u) -eq 0 && $(hostname -s) == lilith-01 ]] || refuse "root on lilith-01 only"
    setup_ops; blackout
    [[ $(ops config-check) == '{"timezone": "Asia/Colombo"}' ]] || refuse "nothing to roll back (config has no Asia/Colombo)"
    (cd "$BK" && sha256sum -c --quiet --strict SHA256SUMS >/dev/null 2>&1) || refuse "backup checksums do not verify"
    say "stop hermes-gateway"; systemctl stop hermes-gateway; wait_stopped || refuse "gateway did not stop"
    rollback_files "$BK" || escalate "rollback files could not be verified"
    start_and_prove utc || escalate "rolled back, but the gateway did not come back healthy"
    echo "TZ_ROLLED_BACK (config.yaml restored exactly; review 30 16 * * * UTC, next 16:30Z; other jobs untouched)"
    ;;
  *) echo "usage: tz_window.sh precheck | change | verify LABEL colombo|utc | rollback BACKUP_DIR" >&2; exit 2 ;;
esac
