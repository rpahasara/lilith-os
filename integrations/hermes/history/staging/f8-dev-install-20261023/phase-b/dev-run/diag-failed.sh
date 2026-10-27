#!/usr/bin/env bash
# READ-ONLY: why is hermes-gateway-dev 'failed' after F8r2's R-1 stop?
set -u
[[ $(hostname) == lilith-dev-01 ]] || { echo "WRONG HOST"; exit 1; }
systemctl show hermes-gateway-dev -p ActiveState,SubState,Result,ExecMainStatus,ExecMainCode,NRestarts,MainPID,InvocationID,FragmentPath,NeedDaemonReload
journalctl -u hermes-gateway-dev --since "2026-10-23 12:31:00" --no-pager -o short-iso | cut -c1-220 | tail -20
B=/var/backups/hermes-gateway-dev; PR=$(ls -d $B/f8r2-preserved-* | tail -1)
echo "--- preserve runtime"; cat $PR/f8r2-runtime.txt; echo "--- R1 log"; cat $PR/f8r2-R1.log | cut -c1-200
