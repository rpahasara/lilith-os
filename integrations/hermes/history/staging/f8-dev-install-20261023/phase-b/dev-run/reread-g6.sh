#!/usr/bin/env bash
# READ-ONLY re-read of the G-5c/G-6/G-6b result file and current unit state.
set -u
[[ $(hostname) == lilith-dev-01 ]] || { echo "WRONG HOST"; exit 1; }
B=/var/backups/hermes-gateway-dev
ls -la --time-style=full-iso $B/G-5c-6b.txt 2>&1; cat $B/G-5c-6b.txt 2>&1
echo "--- now"
for u in hermes-gateway-dev hermes-provider-gate-dev lilith-os-api-dev lilith-memory-broker lilith-authority-dev lilith-recovery-witness; do
  printf '%-26s %s\n' $u "$(for k in ActiveState SubState MainPID NRestarts InvocationID; do systemctl show $u -p $k --value; done | paste -sd' ')"; done
ss -Hltn | awk '{print $4}' | grep -E ':(9901|9911)$'
