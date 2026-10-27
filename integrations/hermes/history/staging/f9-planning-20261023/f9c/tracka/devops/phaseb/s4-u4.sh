STEP=s4-u4
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
# S4 (U-4): console token, verify --full, gateway (+ gate) start; no key, budget still exhausted, ledger unchanged.
LED0=68b4057ef39c7f99d0fc51b26b704bfd936671894a7d523a0952be98d0562e54
ok ledger-before '[[ $(sha256sum < $LED | cut -c1-64) == $LED0 ]]'
bash $P/bin/provision_console_token.sh > $RUN/u4-token.log 2>&1 || die token; tail -1 $RUN/u4-token.log | sed -E 's/[0-9a-f]{20,}/<redacted>/g'
v=$($R/venv/bin/python -I -B $R/bin/verify_release.py --full 2>&1 | tail -1); ok u4-verify '[[ $v == "F8_VERIFY_PASS full f293e72-f9c2" ]]' "$v"
ok env-keys '[[ $(cut -d= -f1 $HH/.env | sort | paste -sd,) == "LILITH_OS_PORT,LILITH_OS_TOKEN" ]]'
systemctl start hermes-gateway-dev || die gateway-start
for _ in $(seq 1 120); do ss -Hltn 'sport = :9901' | grep -q . && ss -Hltn 'sport = :9911' | grep -q . && break; sleep 1; done
ok listeners 'ss -Hltn "sport = :9901" | grep -q 127.0.0.1 && ss -Hltn "sport = :9911" | grep -q 127.0.0.1'
hz=$(bash $R/bin/gate_budget.sh show); echo "gate: $hz"
ok gate-no-key '[[ $hz == *"\"key_loaded\": false"* ]]'
ok gate-exhausted '[[ $hz == *"\"available\": false"* && $hz == *"\"budget_used\": 5"* && $hz == *BUDGET_EXHAUSTED* ]]'
ok ledger-unchanged '[[ $(sha256sum < $LED | cut -c1-64) == $LED0 && $(grep -c ^RESET $LED) -eq 1 ]]' "no initial RESET written"
ok gate-dynamic-owner '[[ $(stat -c %U $LED) != root ]]' "owner=$(stat -c %U:%G $LED)"
for u in hermes-gateway-dev hermes-provider-gate-dev; do echo "$u: $(systemctl show $u -p ActiveState,SubState,NRestarts,MainPID --value | paste -sd' ')"; done
dr5 $R
parity
echo "S4_PASS"
