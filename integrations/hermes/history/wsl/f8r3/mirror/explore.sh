#!/usr/bin/env bash
# Exploratory single-turn run in the WSL mirror (sim only).
set -uo pipefail
W=/root/f8r3; PKGN=hermes-gateway-dev-f293e72-f8r3; HH=/home/lilith/.hermes-dev
bash /root/f8r2/mirror/mirror_setup.sh /root/f8r2/repo /root/f8hd/build/pkg/uv/uv 2>&1 | tail -6
bash $W/mirror/synthprov.sh up
rm -rf /var/tmp/f8 && install -d -m 0700 /var/tmp/f8 && cp $W/out/$PKGN.tar.gz* /var/tmp/f8/ && cd /var/tmp/f8 && tar -xzf $PKGN.tar.gz
P=/var/tmp/f8/$PKGN
bash $P/bin/backup_pre_install.sh | tail -1
F8_SIM=1 bash $P/bin/install.sh > $W/ex-install.log 2>&1; tail -3 $W/ex-install.log
bash $P/bin/provision_console_token.sh
install -o root -g root -m 0600 $W/synth/synthetic-key /etc/hermes-provider-gate-dev/credentials/groq-api-key   # sim stand-in for G-5b
/opt/hermes-gateway-dev/current/venv/bin/python -I -B /opt/hermes-gateway-dev/current/bin/verify_release.py --full
systemctl start hermes-gateway-dev
for i in $(seq 1 45); do ss -Hltn 'sport = :9901' | grep -q . && break; sleep 2; done
for u in hermes-gateway-dev hermes-provider-gate-dev; do echo "$u $(systemctl show $u -p ActiveState,SubState,MainPID --value | paste -sd' ')"; done
ss -Hltnup | grep -E '9901|9911'
curl -s http://127.0.0.1:9911/healthz; echo
sleep 8
TOK=$(grep '^LILITH_OS_TOKEN=' $HH/.env | cut -d= -f2)
curl -s -m 120 -H "X-LILITH-OS-Token: $TOK" -H 'Content-Type: application/json' -d '{"message":"F8-SYNTHETIC explore turn","session":"ex-1"}' http://127.0.0.1:9901/; echo
echo "--- fake requests"; cat $W/synth/requests.jsonl
echo "--- gate log"; journalctl --namespace=hermes-gateway-dev -u hermes-provider-gate-dev -o cat --no-pager | tail -5
echo "--- decisions"; cat $HH/logs/lilith-router-decisions.log 2>&1 | tail -3
echo "--- gateway.log tail"; tail -n 15 $HH/logs/gateway.log | cut -c1-220
echo "--- errors"; tail -n 8 $HH/logs/errors.log 2>/dev/null | cut -c1-220
