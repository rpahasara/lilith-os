#!/usr/bin/env bash
# MIRROR ONLY: minimal reproduction of the OPERATE-profile start failure for a given package (no provider calls).
#   repro_operate.sh <package tarball dir> <release id>
set -u
[[ $(hostname) != lilith-dev-01 ]] || exit 1
OUTD=$1; REL=$2; PKGN=hermes-gateway-dev-$REL; P=/var/tmp/f8/$PKGN; R=/opt/hermes-gateway-dev/current
HH=/home/lilith/.hermes-dev; SY=/root/f8r4/synth; B=/var/backups/hermes-gateway-dev
MS=0; if [[ ! -f /etc/systemd/system/lilith-memory-broker.service ]]; then bash /root/f8r2/mirror/mirror_setup.sh /root/f8r2/repo /root/f8hd/build/pkg/uv/uv >/dev/null 2>&1 && MS=1; fi
for rb in /var/tmp/f8/*/bin/rollback.sh; do [[ -x $rb ]] && bash $rb remove >/dev/null 2>&1; done; systemctl daemon-reload
[[ -d $B ]] && mkdir -p /root/f9b/old && mv $B /root/f9b/old/backups-repro-$(date +%s)
bash /root/f8r4/mirror/synthprov.sh up >/dev/null
rm -rf /var/tmp/f8 && install -d -m 0700 /var/tmp/f8 && cp $OUTD/$PKGN.tar.gz* /var/tmp/f8/ && (cd /var/tmp/f8 && tar -xzf $PKGN.tar.gz)
systemctl start lilith-memory-broker.service lilith-authority-dev.service lilith-recovery-witness.service lilith-os-api-dev.service; sleep 3
bash $P/bin/backup_pre_install.sh >/dev/null; F8_SIM=1 bash $P/bin/install.sh > /tmp/repro-install.log 2>&1 || tail -3 /tmp/repro-install.log
bash $P/bin/provision_console_token.sh >/dev/null
printf '%s\n' "$(cat $SY/synthetic-key)" | script -qec "bash $P/bin/provision_provider_key.sh" /dev/null >/dev/null 2>&1
systemctl start hermes-gateway-dev; sleep 40
echo "-- crash steps: SIGKILL (auto-restart), then SIGTERM restart"
kill -9 "$(systemctl show -p MainPID --value hermes-gateway-dev)"; sleep 45
echo "after SIGKILL: $(systemctl show hermes-gateway-dev -p ActiveState,SubState,NRestarts --value | paste -sd/)"
systemctl restart hermes-gateway-dev; sleep 40
echo "after restart: $(systemctl show hermes-gateway-dev -p ActiveState,SubState,NRestarts --value | paste -sd/)"
echo "== before operate: $(systemctl show hermes-gateway-dev -p ActiveState,SubState --value | paste -sd/)"
F8_SIM=1 bash $P/bin/apply_profile.sh operate 2>&1 | tail -3
sleep 3
echo "== after operate: $(systemctl show hermes-gateway-dev -p ActiveState,SubState,Result,ExecMainStatus --value | paste -sd/)"
systemctl status hermes-gateway-dev --no-pager 2>&1 | grep -E 'ExecStartPre|ExecStart=|status=|Main PID' | head -8
echo "== namespace journal (last 15)"; journalctl --namespace=hermes-gateway-dev -u hermes-gateway-dev -o cat --no-pager -n 15 | cut -c1-220
echo "== system journal for the unit (last 30)"; journalctl -u hermes-gateway-dev -o short-iso --no-pager -n 30 | cut -c1-200
echo "== manual pre-start verify as the unit runs it"; runuser -u lilith -- $R/venv/bin/python -I -B $R/bin/verify_release.py --pre-start 2>&1 | tail -5; echo "rc=$?"
$R/venv/bin/python -I -B $R/bin/verify_release.py --pre-start 2>&1 | tail -5
grep -n 'ExecStartPre' /etc/systemd/system/hermes-gateway-dev.service
bash $R/bin/rollback.sh stop >/dev/null 2>&1; bash $P/bin/rollback.sh remove >/dev/null 2>&1; systemctl daemon-reload
bash /root/f8r4/mirror/synthprov.sh down >/dev/null
[[ $MS == 1 ]] && bash /root/f8r2/mirror/mirror_teardown.sh >/dev/null 2>&1; echo "repro done (mirror restored)"
