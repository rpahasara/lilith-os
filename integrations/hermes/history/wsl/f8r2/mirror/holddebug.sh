#!/usr/bin/env bash
SD=/etc/systemd/system
cp -p $SD/lilith-authority-dev.service /root/f8r2/auth.bak
echo "# probe" >> $SD/lilith-authority-dev.service
echo "authority NeedDaemonReload=$(systemctl show lilith-authority-dev.service -p NeedDaemonReload --value)"
systemctl list-units --all --no-legend --plain | awk '{print $1}' | grep -v '^hermes-gateway-dev' \
  | while read -r u; do [[ $(systemctl show "$u" -p NeedDaemonReload --value 2>/dev/null) == yes ]] && echo "PENDING $u"; done
systemctl list-units --all --no-legend --plain | awk '{print $1}' | grep -c authority
cp -p /root/f8r2/auth.bak $SD/lilith-authority-dev.service; systemctl daemon-reload
echo "after restore+reload=$(systemctl show lilith-authority-dev.service -p NeedDaemonReload --value)"
