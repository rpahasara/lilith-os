#!/usr/bin/env bash
# G-1 + G-1b (DEV, root): backup HERMES_HOME + read-only baseline observation, then the pinned DR-5 as the deployer.
set -uo pipefail
[[ $(hostname) == lilith-dev-01 ]] || { echo "WRONG HOST"; exit 1; }
P=/var/tmp/f8/hermes-gateway-dev-f293e72-f8r2
bash $P/bin/backup_pre_install.sh || { echo G1_FAIL; exit 1; }
PRE=$(ls -d /var/backups/hermes-gateway-dev/pre-* | tail -1)
echo "--- services baseline"; cat $PRE/observation/services | awk '{print $1, $3, $4, $5, $6}'
echo "--- sockets baseline"; cat $PRE/observation/sockets
echo "--- coreapi data"; grep -E ' f |/data' $PRE/observation/coreapi | grep data | cut -c1-140
echo "--- section hashes"; cat $PRE/observation/SECTIONS.sha256
echo "--- G-1b DR-5"
bash $P/bin/dr5_check.sh /var/backups/hermes-gateway-dev/dr5-pre.txt; rc=$?
[[ $rc -eq 0 ]] && echo G1_PASS || echo G1B_FAIL
