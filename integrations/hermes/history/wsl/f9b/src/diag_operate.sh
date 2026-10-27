#!/usr/bin/env bash
# MIRROR ONLY, READ-ONLY: why did the gateway fail to start after apply_profile.sh operate (F9-B rehearsal)?
set -u
[[ $(hostname) != lilith-dev-01 ]] || exit 1
cat /root/f9b/ev/operate.log
Q=$(ls -d /var/backups/hermes-gateway-dev/rollback-* | tail -1); J=$(ls -d $Q/*.hermes-gateway-dev 2>/dev/null | head -1)
echo "== journal dir: $J"
journalctl --directory="$J" -o cat --no-pager 2>/dev/null | grep -E 'F8_VERIFY|Traceback|Error|error' | tail -25
echo "== verify_release config checks"
grep -n -E "config|yaml|level|onboarding|CRITICAL|critical" /root/f9b/build/pkg/bin/verify_release.py | head -60
