#!/usr/bin/env bash
# G-6 re-run (owner Option A, corrected readiness wrapper) -> G-6b probes -> DR-5 + observation parity. NO provider call.
# Waits <= 90 s for 9901, 9911 and the gate START line; output is always saved and printed (no exit inside the log block).
set -uo pipefail
[[ $(hostname) == lilith-dev-01 ]] || { echo "WRONG HOST"; exit 1; }
R=/opt/hermes-gateway-dev/current; P=/var/tmp/f8/hermes-gateway-dev-f293e72-f8r4; B=/var/backups/hermes-gateway-dev
OUT=$B/G-6r-6b.txt
UNITS="lilith-os-api-dev.service lilith-memory-broker.service lilith-memory-broker.socket lilith-authority-dev.service lilith-authority-dev.socket lilith-recovery-witness.service lilith-recovery-witness-owner.socket lilith-recovery-witness-signer.socket lilith-stage3-a2-final.service"
state() { for u in $UNITS; do printf '%s ' "$u"; for k in ActiveState SubState MainPID InvocationID NRestarts ExecMainStartTimestampMonotonic NeedDaemonReload; do printf '%s=%s ' $k "$(systemctl show $u -p $k --value)"; done; echo; done; }
pending() { systemctl list-units --all --no-legend --plain | awk '{print $1}' | while read -r u; do [[ $(systemctl show "$u" -p NeedDaemonReload --value 2>/dev/null) == yes ]] && echo "$u"; done | paste -sd' '; }
listen() { ss -Hltn "sport = :$1" | grep -q .; }
gatelog() { journalctl --namespace=hermes-gateway-dev -u hermes-provider-gate-dev -o cat --no-pager "$@" 2>/dev/null; }
START_RE='"decision": "START"'
main() {
  echo "== G-6 (re-run) $(date -u +%FT%TZ)"
  echo "pre: gw=$(systemctl show hermes-gateway-dev -p ActiveState --value) gate=$(systemctl show hermes-provider-gate-dev -p ActiveState --value) listeners=[$(ss -Hltn | awk '{print $4}' | grep -E ':(9901|9911)$' | paste -sd' ')]"
  local p; p=$(pending); [[ -z $p ]] || { echo "G6_FAIL pending reload before start: $p"; return 1; }
  if ss -Hltn | awk '{print $4}' | grep -qE ':(9901|9911)$'; then echo "G6_FAIL port already listening before start"; return 1; fi
  local before; before=$(state)
  local t0 since; t0=$(date +%s); since=$(date '+%Y-%m-%d %H:%M:%S')
  systemctl start hermes-gateway-dev; local src=$?
  local t9901=- t9911=- tstart=- i
  for i in $(seq 1 90); do
    if [[ $t9901 == - ]] && listen 9901; then t9901=$(( $(date +%s) - t0 )); fi
    if [[ $t9911 == - ]] && listen 9911; then t9911=$(( $(date +%s) - t0 )); fi
    if [[ $tstart == - ]] && gatelog --since "$since" | grep -qF "$START_RE"; then tstart=$(( $(date +%s) - t0 )); fi
    [[ $t9901 != - && $t9911 != - && $tstart != - ]] && break
    sleep 1
  done
  sleep 2
  echo "start_rc=$src ready_after_s: 9901=$t9901 9911=$t9911 gate_START=$tstart (limit 90)"
  local st gst lst
  st=$(for k in ActiveState SubState NRestarts UnitFileState; do systemctl show hermes-gateway-dev -p $k --value; done | paste -sd' ')
  gst=$(for k in ActiveState SubState NRestarts UnitFileState; do systemctl show hermes-provider-gate-dev -p $k --value; done | paste -sd' ')
  lst=$(ss -Hltn | awk '{print $4}' | grep -E ':(9901|9911)$' | sort | paste -sd' ')
  echo "gateway=[$st] gate=[$gst] listeners=[$lst]"
  local G GW; G=$(systemctl show -p MainPID --value hermes-provider-gate-dev); GW=$(systemctl show -p MainPID --value hermes-gateway-dev)
  echo "gate pid=$G gateway pid=$GW"
  echo "gate /proc status: $(grep -E '^(Name|Uid|Gid|CapEff|CapBnd|NoNewPrivs|Seccomp):' /proc/$G/status | tr -s '\t' ' ' | paste -sd';')"
  echo "gate user(ps)=$(ps -o user= -p $G) gateway user(ps)=$(ps -o user= -p $GW)"
  echo "gate START line: $(gatelog --since "$since" | grep -F "$START_RE" | tail -1 | cut -c1-260)"
  echo "socket owners: $(ss -Hltnp | grep -E ':(9901|9911) ' | awk '{print $4, $6}' | paste -sd';')"
  echo "timer=$(systemctl is-active hermes-gateway-dev-retention.timer)/$(systemctl is-enabled hermes-gateway-dev-retention.timer) enabled: gw=$(systemctl is-enabled hermes-gateway-dev) gate=$(systemctl is-enabled hermes-provider-gate-dev)"
  local budget; budget=$(bash $R/bin/gate_budget.sh show); echo "gate_budget: $budget"
  echo "ledger: $(wc -l < /var/lib/private/hermes-provider-gate-dev/ledger.log) line(s); R lines=$(grep -c '^R ' /var/lib/private/hermes-provider-gate-dev/ledger.log)"
  echo "gate FORWARDED lines (all time): $(gatelog | grep -c FORWARDED)"
  p=$(pending); echo "units_pending_reload=[$p]"
  echo "mem gw=$(( $(systemctl show hermes-gateway-dev -p MemoryCurrent --value) / 1048576 ))MiB gate=$(( $(systemctl show hermes-provider-gate-dev -p MemoryCurrent --value) / 1048576 ))MiB host_avail=$(free -m | awk 'NR==2{print $7}')MiB"
  journalctl --namespace=hermes-gateway-dev --since "$since" --no-pager -o cat | grep -E 'F8_VERIFY|Traceback|ERROR' | cut -c1-200
  local after; after=$(state)
  if [[ "$before" == "$after" ]]; then echo "protected services UNCHANGED across start"; else echo "SERVICE_STATE_CHANGED"; diff <(echo "$before") <(echo "$after"); fi
  local uid; uid=$(awk '/^Uid:/{print $2}' /proc/$G/status)
  local ok=1
  [[ $src -eq 0 && $st == "active running 0 static" && $gst == "active running 0 static" && $lst == "127.0.0.1:9901 127.0.0.1:9911" && -z $p && "$before" == "$after" ]] || { ok=0; echo "check: unit/listener/parity criteria not met"; }
  [[ $t9901 != - && $t9911 != - && $tstart != - ]] || { ok=0; echo "check: not ready within 90 s"; }
  (( uid >= 61184 && uid <= 65519 )) || { ok=0; echo "check: gate uid $uid not in the DynamicUser range"; }
  grep -qE '^CapEff:[[:space:]]+0000000000000000$' /proc/$G/status && grep -qE '^NoNewPrivs:[[:space:]]+1$' /proc/$G/status || { ok=0; echo "check: gate caps/NoNewPrivs"; }
  echo "$budget" | grep -q '"key_loaded": true' && echo "$budget" | grep -qE '"budget_used": 0[,}]' && echo "$budget" | grep -q '"budget_requests": 5' && echo "$budget" | grep -q '"available": true' || { ok=0; echo "check: budget not key_loaded/0 of 5/available"; }
  [[ $ok -eq 1 ]] || { echo G6_FAIL; return 1; }
  echo G6_PASS
  echo "== G-6b (no provider call)"
  bash $R/bin/sandbox_probe.sh; local prc=$?
  bash $R/bin/gate_probe.sh; local grc=$?
  echo "budget after probes: $(bash $R/bin/gate_budget.sh show)"
  echo "gate FORWARDED lines after probes: $(gatelog | grep -c FORWARDED)"
  echo "gateway non-loopback established: $(ss -Htnp state established | grep "pid=$GW," | grep -vc 127.0.0.1)"
  echo "gate established (any): $(ss -Htnp state established | grep -c "pid=$G,")"
  echo "== parity"
  local G1; G1=$(ls -d $B/upgrade-pre-* | tail -1)
  bash $P/bin/observe_host.sh $B/g6b-post >/dev/null; bash $P/bin/compare_observations.sh $G1/observation $B/g6b-post; local orc=$?
  bash $P/bin/dr5_check.sh $B/dr5-f8r4-g6b.txt > $B/dr5-f8r4-g6b.summary 2>&1; local drc=$?
  tail -1 $B/dr5-f8r4-g6b.summary
  echo "core api health: $(curl -s -m 5 http://127.0.0.1:8765/health)"
  for u in hermes-gateway-dev hermes-provider-gate-dev lilith-os-api-dev lilith-memory-broker lilith-authority-dev lilith-recovery-witness; do
    printf '%-26s %s\n' $u "$(for k in ActiveState SubState MainPID NRestarts InvocationID; do systemctl show $u -p $k --value; done | paste -sd' ')"; done
  local after2; after2=$(state); [[ "$before" == "$after2" ]] && echo "protected services UNCHANGED across probes" || echo SERVICE_STATE_CHANGED
  if [[ $prc -eq 0 && $grc -eq 0 && $orc -eq 0 && $drc -eq 0 && "$before" == "$after2" ]]; then echo G6B_PASS; else echo "G6B_FAIL prc=$prc grc=$grc orc=$orc drc=$drc"; return 1; fi
}
main > $OUT 2>&1; echo "main_rc=$?" >> $OUT
cat $OUT; echo "OUT_SHA $(sha256sum < $OUT | cut -c1-64)"
