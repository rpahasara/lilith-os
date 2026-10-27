STEP=s2-u1-u2
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
# S2: U-1 preserve F8r4 (quarantines the key + exhausted ledger), U-2 backup + install f9c2, U-2b carry the ledger.
LED0=$(sha256sum < $LED | cut -c1-64); echo "F8r4 ledger before U-1: $LED0"
ok f8r4-ledger-exhausted '[[ $(grep -c "^R " $LED) -ge 5 || $(bash $R/bin/gate_budget.sh show) == *BUDGET_EXHAUSTED* ]]'
F8R4_RELEASE_SHA=$F8R4_SHA bash $P/bin/preserve_f8r4.sh > $RUN/u1.log 2>&1; rc=$?; tail -3 $RUN/u1.log
ok u1 '[[ $rc -eq 0 ]] && grep -q F8R4_PRESERVED $RUN/u1.log'
PRES=$(grep -o "F8R4_PRESERVED [^ ]*" $RUN/u1.log | cut -d" " -f2); Q=$(sed -n "s/^quarantine=//p" $PRES/record)
echo "PRES=$PRES"; echo "Q=$Q"; echo "$PRES" > $RUN/PRES
QLED=$Q/var-lib/private-hermes-provider-gate-dev/ledger.log
ok key-quarantined '[[ ! -e /etc/hermes-provider-gate-dev && -f $Q/etc/hermes-provider-gate-dev/credentials/groq-api-key ]]'
ok ledger-quarantined '[[ $(sha256sum < $QLED | cut -c1-64) == $LED0 ]]'
ok hh-clean '[[ $(ls -A $HH) == memories ]]'
ok gateway-down '! ss -Hltn "sport = :9901" | grep -q . && ! ss -Hltn "sport = :9911" | grep -q .'
parity
bash $P/bin/backup_pre_install.sh > $RUN/u2-backup.log 2>&1 || die backup; tail -1 $RUN/u2-backup.log
bash $P/bin/install.sh > $RUN/u2-install.log 2>&1; rc=$?; tail -2 $RUN/u2-install.log
ok u2 '[[ $rc -eq 0 ]] && grep -q "F8_INSTALL_STAGED f293e72-f9c2" $RUN/u2-install.log'
ok nothing-started '[[ $(systemctl is-active hermes-provider-gate-dev) != active && $(systemctl is-active hermes-gateway-dev) != active ]]'
# U-2b: carry the exhausted ledger forward BEFORE the f9c2 gate first starts (copy; quarantine untouched).
ok no-new-gate-state '[[ ! -e /var/lib/private/hermes-provider-gate-dev && ! -e /var/lib/hermes-provider-gate-dev ]]'
install -d -o root -g root -m 0700 /var/lib/private/hermes-provider-gate-dev
cp -p $QLED $LED || die ledger-copy
ok u2b-ledger '[[ $(sha256sum < $LED | cut -c1-64) == $LED0 && $(sha256sum < $QLED | cut -c1-64) == $LED0 ]]' "$LED0 lines=$(wc -l < $LED) resets=$(grep -c ^RESET $LED)"
parity
echo "S2_PASS"
