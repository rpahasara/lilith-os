#!/usr/bin/env bash
P=/var/tmp/f8/hermes-gateway-dev-f293e72-f8r2; SD=/etc/systemd/system
systemctl start lilith-memory-broker lilith-authority-dev lilith-recovery-witness lilith-os-api-dev
bash $P/bin/backup_pre_install.sh | tail -1
F8_SIM=1 bash $P/bin/install.sh > /root/f8r2/hd2-install.log 2>&1; tail -1 /root/f8r2/hd2-install.log
bash $P/bin/provision_console_token.sh >/dev/null
systemctl start hermes-gateway-dev; sleep 12
cp -p $SD/lilith-authority-dev.service /root/f8r2/auth.bak
echo "# f8r2 pending-reload trigger" >> $SD/lilith-authority-dev.service
echo "pending=$(systemctl show lilith-authority-dev -p NeedDaemonReload --value)"
bash -x $P/bin/rollback.sh remove > /root/f8r2/hd2-rb.log 2>&1; echo "rb rc=$?"
grep -nE "moved=|pending=|HOLD|daemon-reload|F8_ROLL" /root/f8r2/hd2-rb.log | cut -c1-220 | tail -15
cp -p /root/f8r2/auth.bak $SD/lilith-authority-dev.service; systemctl daemon-reload
