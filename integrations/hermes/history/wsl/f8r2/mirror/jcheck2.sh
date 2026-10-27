#!/usr/bin/env bash
systemctl list-units --all --no-legend 'systemd-journald@*' | cut -c1-120
for p in $(pgrep -f 'systemd-journald hermes-gateway-dev'); do echo "pid $p"; ls -l /proc/$p/fd | grep -E 'journal' | awk '{print $NF}' | head -5; done
grep -rl "F8_VERIFY_FAIL" /var/log/journal /var/backups/hermes-gateway-dev /run/log 2>/dev/null | head
journalctl --namespace='*' --no-pager 2>/dev/null | grep -E 'F8_VERIFY_FAIL|FORBIDDEN_KEY' | cut -c1-200 | head
