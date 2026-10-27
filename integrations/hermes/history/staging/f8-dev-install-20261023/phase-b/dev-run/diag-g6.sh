#!/usr/bin/env bash
# READ-ONLY G-6 FAIL diagnosis: gate identity, start timing, listeners, budget (local healthz only; no provider call).
set -u
[[ $(hostname) == lilith-dev-01 ]] || { echo "WRONG HOST"; exit 1; }
G=$(systemctl show -p MainPID --value hermes-provider-gate-dev)
echo "gate MainPID=$G"; grep -E '^(Name|Uid|Gid|PPid|NoNewPrivs|CapEff|Seccomp):' /proc/$G/status
ps -o pid,ppid,uid,user:24,lstart,cmd -p $G | cut -c1-200
echo "children:"; ps -o pid,uid,user:24,cmd --ppid $G | cut -c1-200
systemctl show hermes-provider-gate-dev -p User,DynamicUser,ExecStart,ExecStartPre,ExecMainStartTimestamp,ActiveEnterTimestamp,Type | cut -c1-260
grep -nE '^(User|DynamicUser|Type|ExecStart|ExecStartPre|ExecStartPost)=' /etc/systemd/system/hermes-provider-gate-dev.service
echo "gw ActiveEnter=$(systemctl show hermes-gateway-dev -p ActiveEnterTimestamp --value)"
ss -Hltnp | grep -E ':(9901|9911) '
echo "--- gate journal"
journalctl --namespace=hermes-gateway-dev -u hermes-provider-gate-dev -o short-iso-precise --no-pager | cut -c1-220 | head -20
journalctl -u hermes-provider-gate-dev -o short-iso-precise --no-pager --since "2026-10-23 12:42:00" | cut -c1-220 | head -10
echo "--- budget now"; bash /opt/hermes-gateway-dev/current/bin/gate_budget.sh show
ls -la /var/lib/private/hermes-provider-gate-dev/ 2>&1; wc -l /var/lib/private/hermes-provider-gate-dev/ledger.log 2>&1
