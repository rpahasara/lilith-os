#!/usr/bin/env bash
P=/var/tmp/f8/hermes-gateway-dev-f293e72-f8r2; HH=/home/lilith/.hermes-dev
systemctl start lilith-memory-broker lilith-authority-dev lilith-recovery-witness lilith-os-api-dev
bash $P/bin/backup_pre_install.sh >/dev/null
F8_SIM=1 bash $P/bin/install.sh > /root/f8r2/rd-install.log 2>&1; tail -1 /root/f8r2/rd-install.log
bash $P/bin/provision_console_token.sh >/dev/null
TOK=$(grep '^LILITH_OS_TOKEN=' $HH/.env | cut -d= -f2)
send() { curl -s -m 60 -H "X-LILITH-OS-Token: $TOK" -H 'Content-Type: application/json' -d "{\"message\":\"$1\",\"session\":\"$2\"}" http://127.0.0.1:9901/; echo; }
systemctl start hermes-gateway-dev
for i in $(seq 1 45); do ss -Hltn 'sport = :9901' | grep -q . && break; sleep 1; done; echo "listener after ${i}s"
echo "lifecycle@listen: $(cat $HH/state/gateway.lifecycle.json 2>/dev/null | head -c 300)"
echo "gateway_state@listen: $(cat $HH/gateway_state.json 2>/dev/null | head -c 300)"
send "F8-SYNTHETIC early" race-a
send "/update" race-b
sleep 15
echo "lifecycle@+15: $(cat $HH/state/gateway.lifecycle.json 2>/dev/null | head -c 300)"
echo "gateway_state@+15: $(cat $HH/gateway_state.json 2>/dev/null | head -c 300)"
send "F8-SYNTHETIC later" race-c
send "/update" race-d
send "F8-SYNTHETIC again same session as early" race-a
grep -nE "Gateway running|Press Ctrl|race-|startup|not ready|drain" $HH/logs/gateway.log | cut -c1-200 | head -12
bash $P/bin/rollback.sh remove | tail -1
