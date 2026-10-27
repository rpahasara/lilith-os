#!/usr/bin/env bash
# F8 local simulation of the DEV runbook inside WSL Ubuntu 24.04 (NOT lilith-dev-01). Mirrors DEV's user/paths.
set -uo pipefail
W=/root/f8hd; S=/root/f8sim; REL_ID=f293e72-f8r1; PKGN=hermes-gateway-dev-$REL_ID
s() { echo; echo "=== $* ==="; }
s "SIM-0 mirror DEV preconditions"
getent group lilith >/dev/null || groupadd -g 1002 lilith
id lilith >/dev/null 2>&1 || useradd -u 1001 -g 1002 -m -s /bin/bash lilith
chmod 750 /home/lilith
install -d -o lilith -g lilith -m 700 /home/lilith/.hermes-dev /home/lilith/.hermes-dev/memories
install -d -o root -g root -m 755 /home/lilith/.hermes
install -d -o lilith -g lilith -m 700 /home/lilith/.hermes/lilith-os-dev /home/lilith/.hermes/lilith-os-dev/data
echo sentinel > /home/lilith/.hermes/lilith-os-dev/data/SENTINEL; chown lilith: /home/lilith/.hermes/lilith-os-dev/data/SENTINEL
python3 -c 'import sqlite3; c=sqlite3.connect("/home/lilith/.hermes/lilith-os-dev/data/lilith-dev.db"); c.execute("create table if not exists t(x)"); c.commit()'
chown lilith: /home/lilith/.hermes/lilith-os-dev/data/lilith-dev.db
s "SIM-1 transfer + verify"
rm -rf $S && mkdir -p $S && cd $S
cp $W/out/$PKGN.tar.gz* . && sha256sum -c $PKGN.tar.gz.sha256 && tar -xzf $PKGN.tar.gz && cd $PKGN && sha256sum --quiet -c MANIFEST.sha256 && echo MANIFEST_OK
P=$S/$PKGN
s "G-1 backup"; bash $P/bin/backup_pre_install.sh
s "G-3 install"; F8_SIM=1 bash $P/bin/install.sh; echo "install rc=$?"
REL=/opt/hermes-gateway-dev/releases/$REL_ID
s "G-4 F7 offline suite on Linux (as lilith, temp HOME)"
B=$(mktemp -d /tmp/f8-g4-XXXXXX)
ln -s $REL/src $B/hermes-agent && mkdir $B/hermes-home-dev $B/tests && cp -a $P/home/lilith_router $P/home/plugins $B/hermes-home-dev/   && cp $P/tests/f7-home/config.yaml $B/hermes-home-dev/ && cp $P/tests/f7-home/router.yaml $B/hermes-home-dev/lilith_router/ && cp $P/tests/test_f7_offline.py $B/tests/   && chown -R lilith:lilith $B && chmod 700 $B
runuser -u lilith -- env -i PATH=/usr/bin:/bin HOME=$B PYTHONUNBUFFERED=1 $REL/venv/bin/python -B $B/tests/test_f7_offline.py > /root/f8hd/g4.log 2>&1; echo "G4 rc=$?"; grep -E ' \.\.\. |^Ran |^OK|FAILED' /root/f8hd/g4.log
rm -rf $B
s "G-5 token + full verify"; bash $P/bin/provision_console_token.sh; $REL/venv/bin/python -I -B $REL/bin/verify_release.py --full
s "G-6 start"; systemctl start hermes-gateway-dev; sleep 20
systemctl show hermes-gateway-dev -p ActiveState,SubState,MainPID,NRestarts,MemoryCurrent,ExecMainStatus
ss -Hltnup | grep -E ':9901|python' ; journalctl --namespace=hermes-gateway-dev -u hermes-gateway-dev --no-pager -n 25 | cut -c1-220
s "G-7 smoke phase A"; $REL/venv/bin/python -I -B $REL/bin/smoke_console.py --phase A
systemctl show hermes-gateway-dev -p ActiveState,NRestarts,MemoryCurrent,MemoryPeak,IPEgressPackets,IPIngressPackets
journalctl --namespace=hermes-gateway-dev -u hermes-gateway-dev --no-pager | grep -iE "error|warn|tirith|provider|model" | cut -c1-260 | tail -25
s "SANDBOX probes (inside the unit's namespace, as the service user)"
PID=$(systemctl show -p MainPID --value hermes-gateway-dev)
CG=/sys/fs/cgroup$(cut -d: -f3 /proc/$PID/cgroup)
sh -c "echo \$\$ > $CG/cgroup.procs; exec nsenter -t $PID -m -- setpriv --reuid=1001 --regid=1002 --clear-groups $REL/venv/bin/python -I -c '
import socket
for h,p in ((\"169.254.169.254\",80),(\"1.1.1.1\",443),(\"10.20.0.2\",8765)):
    s=socket.socket(); s.settimeout(3)
    try: s.connect((h,p)); print(\"EGRESS_OPEN\",h,p)
    except OSError as e: print(\"EGRESS_BLOCKED\",h,p,e.errno)
'"
nsenter -t $PID -m -- setpriv --reuid=1001 --regid=1002 --clear-groups sh -c 'ls /home/lilith/.hermes 2>&1; ls /home/lilith; touch /home/lilith/.hermes-dev/lilith_router/x 2>&1; touch /home/lilith/.hermes-dev/config.yaml 2>&1; mv /home/lilith/.hermes-dev/plugins /home/lilith/.hermes-dev/p2 2>&1; touch /opt/hermes-gateway-dev/x 2>&1; ls /etc/hermes-gateway-dev 2>&1; ls /home/lilith/.hermes-dev; echo x >> /home/lilith/.hermes-dev/cron/jobs.json' 2>&1 | head -20
s "WRITES in HERMES_HOME after start"; find /home/lilith/.hermes-dev -newer $REL/RELEASE.sha256 -printf '%M %u %P\n' | sort -k3 | head -80
s "RETENTION"; systemctl start hermes-gateway-dev-retention.service; systemctl show hermes-gateway-dev-retention.service -p Result,ExecMainStatus; journalctl --namespace=hermes-gateway-dev -u hermes-gateway-dev-retention --no-pager -n 5 | cut -c1-200
runuser -u lilith -- /usr/sbin/logrotate -d --state /tmp/f8-lr.state $REL/bin/hermes-logrotate.conf 2>&1 | grep -iE "error|rotating pattern|considering" | head -6
s "SECURITY score"; systemd-analyze security hermes-gateway-dev --no-pager | tail -3
s "R-1 stop"; bash $P/bin/rollback.sh stop
s "R-2 remove"; bash $P/bin/rollback.sh remove
ls -la /opt | grep hermes; ls /etc/systemd/system | grep hermes; ls -la /home/lilith/.hermes-dev; cat /home/lilith/.hermes/lilith-os-dev/data/SENTINEL
echo SIM_DONE
