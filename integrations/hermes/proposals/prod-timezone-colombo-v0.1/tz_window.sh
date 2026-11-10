#!/usr/bin/env bash
# PROD Hermes Asia/Colombo migration (proposal; run only with the owner's explicit authorization). Root on lilith-01.
#   sudo bash tz_window.sh precheck            read-only: every precondition, blackout windows, the planned instant
#   sudo bash tz_window.sh change              precheck, backups, stop gateway, config + review schedule, start gateway
#   sudo bash tz_window.sh verify [label]      read-only post-checks (run at +60 s and +10 min, and after the next review)
#   sudo bash tz_window.sh rollback <backup>   stop gateway, restore config.yaml, review back to "30 16 * * *", start
# The only writes: /root/tz-colombo-<ts>/ (backups), ~/.hermes/config.yaml (one appended line) and the review job's
# schedule in ~/.hermes/cron/jobs.json (through Hermes' own update_job). No other job, reminder, memory, Core API,
# router, unit or credential is touched. Failure: TZ_FAIL.
set -Eeuo pipefail
umask 077
MODE=${1:?usage: tz_window.sh precheck|change|verify [label]|rollback <backup-dir>}
HERE=$(cd "$(dirname "$0")" && pwd)
H=/home/lilith/.hermes; S=$H/hermes-agent; PY=$S/venv/bin/python
CFG=$H/config.yaml; JOBS=$H/cron/jobs.json
CONFIG_PRE_SHA=a6f340f2221130e4d9e142195ce86b8dab9721c0a67c2ca4359950ad39ec37e7   # 2026-11-10 inventory (no timezone key)
declare -A SRC_SHA=(   # PROD Hermes 0.20.5 timezone-relevant sources, byte-identical to the DEV-rehearsed ones
  [hermes_time.py]=3f4ee146597bbb2dabf61ed0458b3e9c7f2dcb9dd89351652cd0fc6e8a7884c8
  [cron/jobs.py]=edf2469d61286ba7ec13ffabddfaef2a9b5e7f51b2ac08c3494eb5ea4aa7177b
  [agent/system_prompt.py]=1d1c1bfbfc3752576f8523bfc5029b8ab3a005a195b2abd10c85ccc9cd20164d
  [gateway/message_timestamps.py]=daa620ef95760d35154d8cf6f6ec6774ea1dbf6b390d101886359d57757fa222
)
die() { echo "TZ_FAIL $*" >&2; exit 1; }
ok() { echo "PASS $*"; }
sha() { sha256sum "$1" | cut -d' ' -f1; }
ops() {   # [VAR=value ...] command [args]: tz_ops.py as lilith with PROD's interpreter; the script arrives on stdin
  local envs=(); while [[ ${1:-} == *=* ]]; do envs+=("$1"); shift; done
  runuser -u lilith -- env -i HOME=/home/lilith HERMES_HOME=$H PATH=/usr/bin:/bin "${envs[@]}" "$PY" -I - "$@" < "$HERE/tz_ops.py"
}
gw() { systemctl show hermes-gateway -p ActiveState -p SubState -p MainPID -p NRestarts | LC_ALL=C sort | paste -sd' '; }

blackout() {   # refuse near the review (16:30Z), the morning brief (02:30Z) and any minute the scheduler is busy
  local m=$((10#$(date -u +%H) * 60 + 10#$(date -u +%M)))
  (( m >= 16 * 60 && m < 17 * 60 )) && die "inside the 16:00-17:00Z review blackout"
  (( m >= 2 * 60 && m < 3 * 60 )) && die "inside the 02:00-03:00Z morning-brief blackout"
  return 0
}

precheck() {
  [[ $(id -u) -eq 0 ]] || die "not root"
  [[ $(hostname -s) == lilith-01 ]] || die "wrong host $(hostname -s)"
  blackout; ok "outside blackout windows ($(date -u +%H:%MZ))"
  local f; for f in "${!SRC_SHA[@]}"; do [[ $(sha "$S/$f") == "${SRC_SHA[$f]}" ]] || die "Hermes source $f changed"; done
  ok "Hermes timezone sources = the DEV-rehearsed bytes"
  [[ $(sha "$CFG") == "$CONFIG_PRE_SHA" ]] || die "config.yaml is not the inventoried a6f340f2 (re-plan)"
  [[ $(stat -c '%U:%G %a' "$CFG") == "lilith:lilith 600" ]] || die "config.yaml owner/mode"
  [[ $(ops config-check) == '{"timezone": null}' ]] || die "config.yaml already has a timezone"
  ok "config.yaml a6f340f2, no timezone key"
  [[ -z $(tr '\0' '\n' < /proc/$(systemctl show -p MainPID --value hermes-gateway)/environ | grep -E '^(HERMES_TIMEZONE|TZ)=') ]] || die "gateway env already has a zone"
  local inv; inv=$(ops jobs-inspect 2>&1) || { echo "$inv" | tail -2 >&2; die "job set differs from the inventory (re-plan)"; }
  ok "job set = the three inventoried recurring jobs, nothing else enabled, all timestamps zone-aware"
  local plan; plan=$(ops jobs-plan) || die "planned review instant"; echo "plan $plan"
  [[ $plan == *'"same_instant": true'* ]] && ok "planned review instant stays 16:30Z" || die "plan"
  [[ $(gw) == *"ActiveState=active"*"SubState=running"* ]] && ok "gateway $(gw)" || die "gateway not running"
  local hb; hb=$(cat $H/cron/ticker_last_success); python3 -c "import time,sys; sys.exit(0 if time.time()-float(sys.argv[1]) < 180 else 1)" "$hb" \
    && ok "scheduler ticked <180 s ago" || die "scheduler not ticking"
  [[ $(systemctl is-active lilith-os-api) == active ]] && ok "Core API active" || die "Core API"
  (( $(df -Pm $H | awk 'NR==2{print $4}') > 500 )) && ok "disk" || die "disk"
  echo "TZ_PRECHECK_PASS"
}

start_gw() {
  systemctl start hermes-gateway
  local i; for i in $(seq 90); do [[ $(gw) == *"ActiveState=active"*"SubState=running"* ]] && break; sleep 1; done
  echo "T_ACTIVE $(date -u +%Y-%m-%dT%H:%M:%S.%3NZ) gateway $(gw)"
  [[ $(gw) == *"ActiveState=active"* ]] || die "gateway did not become active (see the runbook)"
}
stop_gw() {
  echo "T_STOP $(date -u +%Y-%m-%dT%H:%M:%S.%3NZ)"
  systemctl stop hermes-gateway
  local i; for i in $(seq 60); do [[ $(gw) == *"MainPID=0"* ]] && break; sleep 1; done
  [[ $(gw) == *"MainPID=0"* ]] || die "gateway did not stop"
  echo "T_STOPPED $(date -u +%Y-%m-%dT%H:%M:%S.%3NZ) gateway $(gw)"
}

case $MODE in
  precheck) precheck ;;
  change)
    precheck
    BK=/root/tz-colombo-$(date -u +%Y%m%dT%H%M%SZ); install -d -m 0700 "$BK"
    cp -p "$CFG" "$BK/config.yaml"; [[ $(sha "$BK/config.yaml") == "$CONFIG_PRE_SHA" ]] || die "config backup"
    stop_gw                                                       # from here on the scheduler does not write jobs.json
    cp -p "$JOBS" "$BK/jobs.json"; (cd "$BK" && sha256sum config.yaml jobs.json > SHA256SUMS); echo "backup $BK"; cat "$BK/SHA256SUMS"
    restore_and_restart() {                                       # any failure while stopped: exact restore, then start
      echo "TZ_FAIL during change: restoring $BK and restarting" >&2
      install -o lilith -g lilith -m 0600 "$BK/config.yaml" "$CFG.tz-restore" && mv -f "$CFG.tz-restore" "$CFG"
      install -o lilith -g lilith -m 0600 "$BK/jobs.json" "$JOBS.tz-restore" && mv -f "$JOBS.tz-restore" "$JOBS"
      [[ $(sha "$CFG") == "$(sed -n 's/  config.yaml$//p' "$BK/SHA256SUMS")" && $(sha "$JOBS") == "$(sed -n 's/  jobs.json$//p' "$BK/SHA256SUMS")" ]] \
        && echo "restored exactly" >&2 || echo "RESTORE MISMATCH: do not start; escalate" >&2
      systemctl start hermes-gateway; exit 1
    }
    trap restore_and_restart ERR
    ops config-apply "$CFG" "$BK/config.new" >/dev/null
    install -o lilith -g lilith -m 0600 "$BK/config.new" "$CFG.tz-new" && mv -f "$CFG.tz-new" "$CFG"
    [[ $(ops config-check) == '{"timezone": "Asia/Colombo"}' ]] || false
    echo "config.yaml $(sha "$CFG")"
    ops HERMES_TIMEZONE=Asia/Colombo jobs-apply | tee "$BK/jobs-apply.out"
    grep -q '^JOBS_APPLY_OK' "$BK/jobs-apply.out" || false
    trap - ERR
    start_gw
    echo "TZ_CHANGED backup=$BK"
    ;;
  verify)
    L=${2:-check}
    [[ $(hostname -s) == lilith-01 ]] || die "wrong host"
    [[ $(gw) == *"ActiveState=active"*"SubState=running"* ]] && ok "V1 gateway $(gw)" || echo "FAIL V1 gateway $(gw)"
    p=$(systemctl show -p MainPID --value hermes-gateway)
    tr '\0' '\n' < /proc/$p/environ | grep -qx 'HERMES_TIMEZONE=Asia/Colombo' && ok "V2 gateway env HERMES_TIMEZONE=Asia/Colombo (bridged from config)" || echo "FAIL V2 gateway env"
    [[ $(ops config-check) == '{"timezone": "Asia/Colombo"}' ]] && ok "V2 config.yaml timezone Asia/Colombo" || echo "FAIL V2 config"
    ops datecheck | sed 's/^/V3 /'
    ops jobs-inspect | "$PY" -I -c '
import json, sys, datetime as dt
j = {x["id"]: x for x in json.load(sys.stdin)}
r = j["e161234245f3"]; n = dt.datetime.fromisoformat(r["next_run_at"])
ok = r["expr"] == "0 22 * * *" and n.utcoffset() == dt.timedelta(hours=5, minutes=30) and (n.astimezone(dt.timezone.utc).hour, n.astimezone(dt.timezone.utc).minute) == (16, 30)
print(("PASS" if ok else "FAIL") + " V4 review", r["expr"], r["next_run_at"], "=", n.astimezone(dt.timezone.utc).isoformat())
now = dt.datetime.now(dt.timezone.utc)
for jid, name in (("5365cfb456d4", "commitment-sync"), ("f56407e4cef8", "snapshot")):
    last = dt.datetime.fromisoformat(j[jid]["last_run_at"]); age = (now - last).total_seconds()
    lim = 150 if jid == "5365cfb456d4" else 700
    print(("PASS" if age < lim and j[jid]["last_status"] == "ok" else "FAIL"), "V5", name, "last", j[jid]["last_run_at"], j[jid]["last_status"], "next", j[jid]["next_run_at"])'
    hb=$(cat $H/cron/ticker_last_success); python3 -c "import time,sys; a=time.time()-float(sys.argv[1]); print(('PASS' if a < 180 else 'FAIL'), 'V5 scheduler ticked', round(a), 's ago')" "$hb"
    grep -aE "Gateway running with|✓ (telegram|discord|lilith_os) (connected|reconnected)" $H/logs/gateway.log 2>/dev/null | tail -4 | sed 's/^/V6 /'
    [[ $(systemctl is-active lilith-os-api) == active ]] && ok "V7 Core API active" || echo "FAIL V7 Core API"
    echo "TZ_VERIFY_DONE $L $(date -u +%Y-%m-%dT%H:%M:%SZ)"
    ;;
  rollback)
    BK=${2:?backup dir}; [[ -f $BK/config.yaml && -f $BK/SHA256SUMS ]] || die "backup dir"
    [[ $(hostname -s) == lilith-01 ]] || die "wrong host"
    blackout
    stop_gw
    install -o lilith -g lilith -m 0600 "$BK/config.yaml" "$CFG.tz-restore" && mv -f "$CFG.tz-restore" "$CFG"
    [[ $(sha "$CFG") == "$CONFIG_PRE_SHA" ]] || die "config restore mismatch (gateway left stopped; escalate)"
    ops jobs-revert | tee "$BK/jobs-revert.out"
    grep -q '^JOBS_REVERT_OK' "$BK/jobs-revert.out" || die "review revert failed (gateway left stopped; escalate)"
    start_gw
    echo "TZ_ROLLED_BACK (config a6f340f2 restored; review 30 16 * * * UTC; other jobs untouched)"
    ;;
  *) die "unknown mode $MODE" ;;
esac
