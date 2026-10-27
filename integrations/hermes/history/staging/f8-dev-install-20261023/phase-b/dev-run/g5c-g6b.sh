#!/usr/bin/env bash
# G-5c verify with key (key never printed) -> G-6 start gateway (+gate, timer) -> G-6b sandbox + gate probes. NO provider call.
set -uo pipefail
[[ $(hostname) == lilith-dev-01 ]] || { echo "WRONG HOST"; exit 1; }
R=/opt/hermes-gateway-dev/current; B=/var/backups/hermes-gateway-dev; F=/etc/hermes-provider-gate-dev/credentials/groq-api-key
UNITS="lilith-os-api-dev.service lilith-memory-broker.service lilith-memory-broker.socket lilith-authority-dev.service lilith-authority-dev.socket lilith-recovery-witness.service lilith-recovery-witness-owner.socket lilith-recovery-witness-signer.socket lilith-stage3-a2-final.service"
state() { for u in $UNITS; do printf '%s ' "$u"; for k in ActiveState SubState MainPID InvocationID NRestarts ExecMainStartTimestampMonotonic NeedDaemonReload; do printf '%s=%s ' $k "$(systemctl show $u -p $k --value)"; done; echo; done; }
{
echo "== G-5c"
[[ -f $F ]] || { echo "G5C_FAIL key file absent"; exit 1; }
echo "key file: $(stat -c '%U:%G %a %s bytes' $F) dir=$(stat -c '%U:%G %a' $(dirname $F)) entries=$(ls -A $(dirname $F) | wc -l)"
echo "key sha256_prefix=$(tr -d '\n' < $F | sha256sum | cut -c1-12) format_ok=$(grep -qE '^gsk_[A-Za-z0-9]{20,}$' $F && echo yes || echo no)"
$R/venv/bin/python -I -B $R/bin/verify_release.py --full || { echo G5C_FAIL; exit 1; }
[[ $(stat -c '%U %a' $F) == "root 600" && $(stat -c '%U %a' $(dirname $F)) == "root 700" ]] || { echo "G5C_FAIL modes"; exit 1; }
echo G5C_PASS
echo "== G-6"
pending=$(systemctl list-units --all --no-legend --plain | awk '{print $1}' | while read -r u; do [[ $(systemctl show "$u" -p NeedDaemonReload --value 2>/dev/null) == yes ]] && echo "$u"; done | paste -sd' ')
[[ -z $pending ]] || { echo "G6_FAIL pending reload before start: $pending"; exit 1; }
before=$(state)
systemctl start hermes-gateway-dev; src=$?
for i in $(seq 1 45); do ss -Hltn 'sport = :9901' | grep -q . && break; sleep 2; done
sleep 3
st=$(for k in ActiveState SubState NRestarts UnitFileState; do systemctl show hermes-gateway-dev -p $k --value; done | paste -sd' ')
gst=$(for k in ActiveState SubState NRestarts UnitFileState; do systemctl show hermes-provider-gate-dev -p $k --value; done | paste -sd' ')
lst=$(ss -Hltn | awk '{print $4}' | grep -E ':(9901|9911)$' | sort | paste -sd' ')
echo "start_rc=$src gateway=[$st] gate=[$gst] listeners=[$lst] listen_after~$((i*2))s"
echo "gateway pid=$(systemctl show -p MainPID --value hermes-gateway-dev) gate pid=$(systemctl show -p MainPID --value hermes-provider-gate-dev) user=$(ps -o user= -p $(systemctl show -p MainPID --value hermes-provider-gate-dev))"
echo "timer=$(systemctl is-active hermes-gateway-dev-retention.timer)/$(systemctl is-enabled hermes-gateway-dev-retention.timer) enabled(gw)=$(systemctl is-enabled hermes-gateway-dev) enabled(gate)=$(systemctl is-enabled hermes-provider-gate-dev)"
budget=$(bash $R/bin/gate_budget.sh show); echo "gate_budget: $budget"
pending=$(systemctl list-units --all --no-legend --plain | awk '{print $1}' | while read -r u; do [[ $(systemctl show "$u" -p NeedDaemonReload --value 2>/dev/null) == yes ]] && echo "$u"; done | paste -sd' ')
echo "units_pending_reload=[${pending}]"
echo "mem gw=$(( $(systemctl show hermes-gateway-dev -p MemoryCurrent --value) / 1048576 ))MiB host_avail=$(free -m | awk 'NR==2{print $7}')MiB"
journalctl --namespace=hermes-gateway-dev --no-pager -o cat | grep -E 'F8_VERIFY|Traceback|ERROR' | cut -c1-200
after=$(state)
if [[ "$before" == "$after" ]]; then echo "protected services UNCHANGED across start"; else echo "SERVICE_STATE_CHANGED"; diff <(echo "$before") <(echo "$after"); fi
ok=1
[[ $src -eq 0 && $st == "active running 0 static" && $gst == "active running 0 static" && $lst == "127.0.0.1:9901 127.0.0.1:9911" && -z $pending && "$before" == "$after" ]] || ok=0
echo "$budget" | grep -q '"key_loaded": *true' && echo "$budget" | grep -q '"budget_used": *0[,}]' && echo "$budget" | grep -q '"available": *true' || ok=0
[[ $ok -eq 1 ]] && echo G6_PASS || { echo G6_FAIL; exit 1; }
echo "== G-6b"
bash $R/bin/sandbox_probe.sh; prc=$?
bash $R/bin/gate_probe.sh; grc=$?
echo "budget after probes: $(bash $R/bin/gate_budget.sh show)"
after2=$(state); [[ "$before" == "$after2" ]] && echo "protected services UNCHANGED across probes" || echo SERVICE_STATE_CHANGED
[[ $prc -eq 0 && $grc -eq 0 && "$before" == "$after2" ]] && echo G6B_PASS || echo G6B_FAIL
} > $B/G-5c-6b.txt 2>&1
cat $B/G-5c-6b.txt; echo "OUT_SHA $(sha256sum < $B/G-5c-6b.txt | cut -c1-64)"
