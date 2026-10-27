#!/usr/bin/env bash
# READ-ONLY diagnosis of G-7b P7 (no change on DEV). Re-reads the saved probe output (plink-crash rule).
set -u
[[ $(hostname) == lilith-dev-01 ]] || { echo "WRONG HOST"; exit 1; }
echo "--- saved probe (re-read)"; cat /var/backups/hermes-gateway-dev/G-7b-probe.txt | grep -E 'P1 |P7|P8|F8_PROBE'
echo "--- saved smoke tail"; tail -1 /var/backups/hermes-gateway-dev/G-7-smoke.txt
echo "--- /etc/hosts entries for metadata"; grep -n -i 'metadata\|169.254' /etc/hosts
echo "--- nsswitch hosts"; grep '^hosts' /etc/nsswitch.conf
echo "--- gateway"; for k in ActiveState SubState NRestarts MainPID IPEgressBytes IPIngressBytes; do printf '%s=%s ' $k "$(systemctl show hermes-gateway-dev -p $k --value)"; done; echo
echo "--- G-8 not yet run: $(systemctl show hermes-gateway-dev-retention.service -p Result,ActiveState --value | paste -sd' ')"
