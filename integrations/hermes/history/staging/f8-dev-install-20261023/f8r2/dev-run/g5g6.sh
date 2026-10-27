#!/usr/bin/env bash
# G-5 (DEV-only console token, never printed; full verify) + G-6 (start; health; existing services unchanged).
set -uo pipefail
[[ $(hostname) == lilith-dev-01 ]] || { echo "WRONG HOST"; exit 1; }
P=/var/tmp/f8/hermes-gateway-dev-f293e72-f8r2; R=/opt/hermes-gateway-dev/current
UNITS="lilith-os-api-dev.service lilith-memory-broker.service lilith-memory-broker.socket lilith-authority-dev.service lilith-authority-dev.socket lilith-recovery-witness.service lilith-recovery-witness-owner.socket lilith-recovery-witness-signer.socket lilith-stage3-a2-final.service"
state() { for u in $UNITS; do printf '%s ' "$u"; for k in ActiveState SubState MainPID InvocationID NRestarts ExecMainStartTimestampMonotonic NeedDaemonReload; do printf '%s=%s ' $k "$(systemctl show $u -p $k --value)"; done; echo; done; }
bash $P/bin/provision_console_token.sh || { echo G5_FAIL; exit 1; }
$R/venv/bin/python -I -B $R/bin/verify_release.py --full || { echo G5_FAIL; exit 1; }
[[ ! -e /etc/hermes-gateway-dev/provider.env ]] && echo "provider.env ABSENT (Phase A)"
echo G5_PASS
before=$(state)
systemctl start hermes-gateway-dev; src=$?
for i in $(seq 1 45); do ss -Hltn 'sport = :9901' | grep -q . && break; sleep 2; done
st=$(for k in ActiveState SubState NRestarts UnitFileState; do systemctl show hermes-gateway-dev -p $k --value; done | paste -sd' ')
lst=$(ss -Hltnup | grep '"hermes"' | awk '{print $1, $5}' | paste -sd';')
echo "start_rc=$src state=[$st] listeners=[$lst] listen_after~$((i*2))s"
echo "timer=$(systemctl is-active hermes-gateway-dev-retention.timer) enabled(gw)=$(systemctl is-enabled hermes-gateway-dev) enabled(timer)=$(systemctl is-enabled hermes-gateway-dev-retention.timer)"
echo "mem=$(( $(systemctl show hermes-gateway-dev -p MemoryCurrent --value) / 1048576 ))MiB host_avail=$(free -m | awk 'NR==2{print $7}')MiB"
pending=$(systemctl list-units --all --no-legend --plain | awk '{print $1}' | while read -r u; do [[ $(systemctl show "$u" -p NeedDaemonReload --value 2>/dev/null) == yes ]] && echo "$u"; done | paste -sd' ')
echo "units_pending_reload=[${pending}]"
journalctl --namespace=hermes-gateway-dev -u hermes-gateway-dev --no-pager | grep -E 'F8_VERIFY|Traceback|ERROR' | cut -c1-200
grep -E 'lilith_os|Gateway running|Press Ctrl' /home/lilith/.hermes-dev/logs/gateway.log | cut -c1-160
after=$(state)
if [[ "$before" == "$after" ]]; then echo "existing services UNCHANGED across start"; else echo "SERVICE_STATE_CHANGED"; diff <(echo "$before") <(echo "$after"); fi
[[ $src -eq 0 && $st == "active running 0 static" && $lst == "tcp 127.0.0.1:9901" && -z $pending && "$before" == "$after" ]] && echo G6_PASS || echo G6_FAIL
