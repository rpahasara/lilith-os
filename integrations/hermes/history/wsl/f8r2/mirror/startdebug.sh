#!/usr/bin/env bash
P=/var/tmp/f8/hermes-gateway-dev-f293e72-f8r2; HH=/home/lilith/.hermes-dev
systemctl daemon-reload   # clear the global NeedDaemonReload left by the enable --no-reload finding (sim environment)
systemctl start lilith-memory-broker lilith-authority-dev lilith-recovery-witness lilith-os-api-dev
bash $P/bin/backup_pre_install.sh | tail -1
F8_SIM=1 bash $P/bin/install.sh > /root/f8r2/sd-install.log 2>&1; tail -1 /root/f8r2/sd-install.log
bash $P/bin/provision_console_token.sh >/dev/null
systemctl start hermes-gateway-dev
for t in 10 20 40 60 90; do sleep 10; ss -Hltn 'sport = :9901' | grep -q . && { echo "listening by ~${t}s"; break; }; done
ss -Hltnp | grep hermes
echo "--- gateway.log/errors.log tail"; tail -n 25 $HH/logs/gateway.log 2>/dev/null | cut -c1-220; tail -n 10 $HH/logs/errors.log 2>/dev/null | cut -c1-220
PID=$(systemctl show -p MainPID --value hermes-gateway-dev); echo "threads: $(ls /proc/$PID/task | wc -l)"; cat /proc/$PID/wchan; echo
for t in /proc/$PID/task/*; do echo "$(cat $t/comm) $(cat $t/wchan)"; done | sort | uniq -c | head
bash $P/bin/rollback.sh remove | tail -1
