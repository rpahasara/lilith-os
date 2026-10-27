#!/usr/bin/env bash
# MIRROR ONLY: after the first rehearsal stopped at U-3 (old installer), rehearse R-2 + R-3 with NO erasure epoch
# (the whole preserved inventory, conversation state included, must come back identical), then clean the mirror.
set -uo pipefail
[[ $(hostname) != lilith-dev-01 ]] || exit 1
W=/root/f9ca; EV=$W/rehearsal-ev; P9=/var/tmp/f8/hermes-gateway-dev-f293e72-f9c1; R=/opt/hermes-gateway-dev/current
CORE=/home/lilith/.hermes/lilith-os-dev; RES=$W/restore-noerase.tsv; : > $RES
rec() { printf '%s\t%s\t%s\n' "$1" "$2" "$3" | tee -a "$RES"; }
PRES=$(ls -d /var/backups/hermes-gateway-dev/f8r4-preserved-* | tail -1)
[[ -e /var/lib/hermes-forget ]] && rec pre INFO "hermes-forget state present: $(ls /var/lib/hermes-forget)" || rec pre INFO "no F9-C state, no erasure epoch"
bash $R/bin/rollback.sh remove > $EV/ne-r2.log 2>&1 && grep -q F8_ROLLBACK_REMOVED $EV/ne-r2.log && rec NE-R2 PASS "$(tail -1 $EV/ne-r2.log | cut -c1-120)" || rec NE-R2 FAIL "$(tail -3 $EV/ne-r2.log | tr '\n' ' ')"
F8_SIM=1 bash $P9/bin/restore_f8r4.sh "$PRES" > $EV/ne-r3.log 2>&1 && grep -q F8R4_RESTORED $EV/ne-r3.log \
  && rec NE-R3 PASS "$(grep -E '^inventory:|F8R4_RESTORED' $EV/ne-r3.log | paste -sd' ' | cut -c1-260)" || rec NE-R3 FAIL "$(tail -4 $EV/ne-r3.log | tr '\n' ' ' | cut -c1-400)"
n=$(grep -rlaF F9CA-CANARY-F8R4 /home/lilith/.hermes-dev 2>/dev/null | wc -l)
rec NE-R3-state INFO "F8r4 conversation canary files restored into HERMES_HOME: $n (no FORGET ran: must be restored exactly)"
c=$(curl -s -m 170 -o /dev/null -w '%{http_code}' -H 'Content-Type: application/json' -d '{"message":"TEST_ONLY after no-erase restore","session":"f9ca-ne"}' http://127.0.0.1:8765/os/conversation)
rec NE-R3-turn INFO "restored F8r4 relay http=$c"
bash $P9/bin/dr5_check.sh $EV/dr5-ne.txt > $EV/dr5-ne-check.txt && rec NE-DR5 PASS "$(tail -1 $EV/dr5-ne-check.txt | cut -c1-48)" || rec NE-DR5 FAIL ""
echo "#### cleanup"
bash $R/bin/rollback.sh remove > $EV/ne-cleanup.log 2>&1
rm -rf $CORE/releases/f9ca-f9c1 /opt/f9ca-mirror /usr/local/lib/f9ca-mirror /tmp/f9ca-signal /etc/lilith-os-dev/privacy-authority.key /var/lib/hermes-forget /run/hermes-forget
CORE0=b9eb32c2e1756b23f5d1f28fa0c2e3b9a1ab35e6
ln -sfn $CORE/releases/$CORE0 $CORE/current.new && chown -h lilith:lilith $CORE/current.new && mv -Tf $CORE/current.new $CORE/current
systemctl daemon-reload
bash /root/f8r4/mirror/synthprov.sh down >/dev/null
bash /root/f8r2/mirror/mirror_teardown.sh > $EV/ne-teardown.log 2>&1; rec teardown INFO "$(tail -1 $EV/ne-teardown.log)"
rec final INFO "HH=[$(ls -A /home/lilith/.hermes-dev | tr '\n' ' ')] units=[$(systemctl list-units --all --no-legend 'hermes*' 'lilith*' | wc -l)]"
