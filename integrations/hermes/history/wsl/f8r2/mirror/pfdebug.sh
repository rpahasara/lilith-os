#!/usr/bin/env bash
P=/var/tmp/f8/hermes-gateway-dev-f293e72-f8r2; HH=/home/lilith/.hermes-dev
bash $P/bin/backup_pre_install.sh | tail -1
F8_SIM=1 bash $P/bin/install.sh > /root/f8r2/pfdebug-install.log 2>&1; tail -1 /root/f8r2/pfdebug-install.log
bash $P/bin/provision_console_token.sh
sed -i 's/^cognitive_enabled: false/cognitive_enabled: true/' $HH/lilith_router/router.yaml
systemctl start hermes-gateway-dev; echo "start rc=$?"; sleep 3
systemctl show hermes-gateway-dev -p ActiveState,Result,ExecMainStatus,ExecMainCode,NRestarts
systemctl status hermes-gateway-dev --no-pager -n 0 | head -12
echo "--- namespace journal"; journalctl --namespace=hermes-gateway-dev --no-pager -n 20 | cut -c1-200
echo "--- main journal"; journalctl --no-pager -n 10 -u hermes-gateway-dev | cut -c1-200
echo "--- direct gate run"; /opt/hermes-gateway-dev/current/venv/bin/python -I -B /opt/hermes-gateway-dev/current/bin/verify_release.py --pre-start
bash $P/bin/rollback.sh remove | tail -1
