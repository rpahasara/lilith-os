STEP=s3-b2-u3
# Shared header for every Phase B step (pasted into each step by build; kept identical).
set -uo pipefail
[[ $(hostname) == lilith-dev-01 ]] || { echo "WRONG HOST $(hostname)"; exit 1; }
[[ $(id -u) -eq 0 ]] || { echo "NOT ROOT"; exit 1; }
RUN=/var/tmp/f8/f9c2-run; install -d -o root -g root -m 0700 /var/tmp/f8 $RUN
exec > >(tee -a "$RUN/${STEP}.out") 2>&1
CORE=/home/lilith/.hermes/lilith-os-dev; HH=/home/lilith/.hermes-dev; B=/var/backups/hermes-gateway-dev
N=hermes-gateway-dev-f293e72-f9c2; P=/var/tmp/f8/$N; R=/opt/hermes-gateway-dev/current
PKG_SHA=4b0b0110dde1cccd585203ea9a92cfe8b8cbe31d8e1a6e4edb461ba2c09c3ba5; MANIFEST_SHA=c78a8bd2d00c80dc3c3cca5f2dac3cd55a748405412730e48f68e0b3e9ff46dd
CORE_SHA=3f6b909f8b4c73a132c49626da585ee998cddda1; F8R4_SHA=7343b245f62ecf3ee70be860a55e550c4a0e14f9192ac21c3ed8f373cc8b2bd9
LED=/var/lib/private/hermes-provider-gate-dev/ledger.log; INTENT=/var/lib/hermes-forget/intent/first-interaction.intent
MARK=/var/lib/hermes-forget/in-progress; CAN=F9C2-DEV-CANARY
die() { echo "STEP_FAIL ${STEP} $*"; exit 1; }
ok() { if eval "$2"; then echo "OK $1 ${3:-}"; else die "$1 ${3:-}"; fi; }
pids() { for u in lilith-memory-broker.service lilith-authority-dev.service lilith-recovery-witness.service; do
  printf '%s=%s ' "${u%%.service}" "$(systemctl show $u -p MainPID,NRestarts,ActiveState --value | paste -sd/)"; done; echo; }
parity() { ok protected-parity '[[ $(pids) == "lilith-memory-broker=3411/0/active lilith-authority-dev=128648/0/active lilith-recovery-witness=127192/0/active " ]]' "$(pids)"; }
dr5() { local d; d=$(bash ${1:-$R}/bin/dr5_check.sh "$RUN/dr5-${STEP}.txt" 2>&1 | tr '\n' ' '); ok dr5 '[[ $d == *F8_DR5_EQUAL* ]]' "$(echo $d | grep -o 'F8_DR5_[A-Z]*' | head -1)"; }
echo "=== ${STEP} $(date -u +%Y-%m-%dT%H:%M:%SZ) boot=$(cut -c1-8 /proc/sys/kernel/random/boot_id)"
# S3: B-2a/B-2b drill store (lilith), U-3 install_f9c, U-3b the ONE approved Core API restart.
ok release-f9c2 '[[ $(basename "$(readlink -f $R)") == f293e72-f9c2 && -f $R/bin/f9c_dev_drill.py ]]'
ok drill-absent '[[ ! -e $CORE/f9-drill ]]'
install -d -o lilith -g lilith -m 0700 $CORE/f9-drill
runuser -u lilith -- env -C /tmp HOME=/tmp $CORE/api-venv/bin/python -I -B $R/bin/f9c_dev_drill.py --core-api $CORE/current provision > $RUN/b2-provision.json 2>&1
cat $RUN/b2-provision.json
ok b2-provision 'grep -q "\"status\": \"PROVISIONED\"" $RUN/b2-provision.json && grep -q "\"floorAdded\": true" $RUN/b2-provision.json'
ok b2-files '[[ $(stat -c "%U %a" $CORE/f9-drill/privacy_governance.f9drill.db $CORE/f9-drill/privacy-authority.f9drill.key | sort -u) == "lilith 600" ]]'
ok probe-clean '[[ ! -e $CORE/data/privacy_governance.dev.db && ! -e $CORE/data/cognitive_memory.dev.db && ! -e $CORE/data/canonical-durability-probe ]]'
F9C_CORE_API_DIR=$CORE/current/lilith_memory bash $P/bin/install_f9c.sh > $RUN/u3-install-f9c.log 2>&1; rc=$?; tail -2 $RUN/u3-install-f9c.log
ok u3 '[[ $rc -eq 0 ]] && grep -q "F9C_INSTALLED f293e72-f9c2" $RUN/u3-install-f9c.log'
ok coreapi-copy 'cmp -s /etc/hermes-forget/coreapi/lilith_memory/privacy_governance.py $CORE/current/lilith_memory/privacy_governance.py'
for u in hermes-forget.path hermes-forget-hold.path hermes-forget-reconcile.timer; do ok "unit-$u" '[[ $(systemctl is-active $u) == active ]]'; done
parity
pid0=$(systemctl show lilith-os-api-dev -p MainPID --value)
systemctl restart lilith-os-api-dev || die restart
for _ in $(seq 1 30); do h=$(curl -s -m 3 http://127.0.0.1:8765/health); [[ $h == *'"status":"ok"'* ]] && break; sleep 2; done
pid1=$(systemctl show lilith-os-api-dev -p MainPID --value)
ok u3b-health '[[ $h == *"\"status\":\"ok\""* && $pid1 != $pid0 && $pid1 != 0 ]]' "pid $pid0 -> $pid1 $h"
G=$(getent group lilith-forget | cut -d: -f3)
ok u3b-group 'grep -qw "$G" <(grep ^Groups: /proc/$pid1/status)' "gid=$G"
ok coreapi-still-expected '[[ $(basename "$(readlink -f $CORE/current)") == $CORE_SHA ]]'
parity
echo "S3_PASS"
