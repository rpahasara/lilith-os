STEP=s6-precheck
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
# S6 (D-2 precondition, READ-ONLY): current state and the exact erasure inventory still equal the accepted scope.
LED0=68b4057ef39c7f99d0fc51b26b704bfd936671894a7d523a0952be98d0562e54
F8R2_ITEMS=d2a4c92c66a829b16a3fba1ce8aca83f598ba68de0c93b93728957f8429221c5
PY=$R/python/cpython-3.11.16-linux-x86_64-gnu/bin/python3.11
CFG=/etc/hermes-forget/executor.json
ok release '[[ $(basename "$(readlink -f $R)") == f293e72-f9c2 ]]'
ok coreapi-release '[[ $(basename "$(readlink -f $CORE/current)") == $CORE_SHA ]]'
h=$(curl -s -m 5 http://127.0.0.1:8765/health); ok coreapi-health '[[ $h == *"\"status\":\"ok\""* ]]'
ok coreapi-pid '[[ $(systemctl show lilith-os-api-dev -p MainPID,NRestarts --value | paste -sd/) == 268361/0 ]]' "since U-3b"
ok gateway '[[ $(systemctl show hermes-gateway-dev -p MainPID,ActiveState --value | paste -sd/) == 268515/active ]]'
ok gate '[[ $(systemctl show hermes-provider-gate-dev -p MainPID,ActiveState --value | paste -sd/) == 268511/active ]]'
ok no-intent '[[ ! -e $INTENT ]]'; ok no-marker '[[ ! -e $MARK ]]'
RD=$(python3 -c 'import json;print(json.load(open("/etc/hermes-forget/executor.json"))["receiptDir"])')
EL=$(python3 -c 'import json;print(json.load(open("/etc/hermes-forget/executor.json"))["epochLog"])')
ok no-receipts '[[ $(find $RD -type f 2>/dev/null | wc -l) -eq 0 ]]' "receiptDir=$RD"
ok no-epochs '[[ ! -s $EL ]]' "epochLog=$EL"
st=$(runuser -u lilith -- env -C /tmp HOME=/tmp $CORE/api-venv/bin/python -I -B $R/bin/f9c_dev_drill.py --core-api $CORE/current status 2>&1)
echo "drill status: $st"
ok drill-idle '[[ $st == *"\"inFlight\": false"* && $st == *"\"completed\": false"* ]]'
ok ledger '[[ $(sha256sum < $LED | cut -c1-64) == $LED0 ]]'
hz=$(bash $R/bin/gate_budget.sh show); ok budget '[[ $hz == *"\"budget_used\": 5"* && $hz == *"\"key_loaded\": false"* && $hz == *BUDGET_EXHAUSTED* ]]'
for u in hermes-forget.path hermes-forget-hold.path hermes-forget-reconcile.timer; do ok "unit-$u" '[[ $(systemctl is-active $u) == active ]]'; done
ok no-pending-reload '[[ -z $(systemctl show "*" -p Id,NeedDaemonReload 2>/dev/null | grep -B1 "NeedDaemonReload=yes") ]]'
ok probe-clean '[[ ! -e $CORE/data/privacy_governance.dev.db && ! -e $CORE/data/cognitive_memory.dev.db && ! -e $CORE/data/canonical-durability-probe ]]'
echo "--- inventory (executor scan_backups)"
inv=$($PY -I -B - "$R/bin" "$B" <<'PY'
import sys, collections, hashlib
sys.path.insert(0, sys.argv[1]); import hermes_forget_executor as X
root = X.Path(sys.argv[2]); items = X.scan_backups(root)
c = collections.Counter((str(i.path.relative_to(root)).split("/")[0], i.kind) for i in items)
print(";".join(f"{t}:{k}:{n}" for (t, k), n in sorted(c.items())))
f8r2 = []
full = []
for i in items:
    rel = str(i.path.relative_to(root)); top = rel.split("/")[0]
    full.append(f"{i.kind} {i.size} {i.sha256} {rel}{('!' + i.member) if i.member else ''}")
    if top in ("rollback-20261023T123157Z", "upgrade-pre-20261023T123016Z"):
        sub = rel.split("/", 1)[1] if "/" in rel else rel
        f8r2.append(f"{i.kind} {i.size} {i.sha256[:16]} {sub}{('!' + i.member) if i.member else ''}")
print(len(items), hashlib.sha256(("\n".join(sorted(f8r2)) + "\n").encode()).hexdigest(),
      hashlib.sha256(("\n".join(sorted(full)) + "\n").encode()).hexdigest())
PY
)
echo "$inv"
ok inv-counts '[[ $(head -1 <<<"$inv") == "rollback-20261023T123157Z:HERMES_HOME_CONVERSATION:18;rollback-20261023T123157Z:JOURNAL_COPY:1;rollback-20261023T123157Z:STATE_DB:3;rollback-20261025T082553Z:HERMES_HOME_CONVERSATION:27;rollback-20261025T082553Z:JOURNAL_COPY:1;rollback-20261025T082553Z:STATE_DB:3;upgrade-pre-20261023T123016Z:TAR_MEMBER:20" ]]'
ok inv-total '[[ $(sed -n 2p <<<"$inv" | cut -d" " -f1) == 73 ]]'
ok inv-f8r2-exact '[[ $(sed -n 2p <<<"$inv" | cut -d" " -f2) == $F8R2_ITEMS ]]' "42 F8r2 items byte-identical to the verified scope"
echo "--- live store"
live=$(python3 - "$HH/state.db" "$CAN" <<'PY'
import sqlite3, sys
c = sqlite3.connect("file:" + sys.argv[1] + "?mode=ro", uri=True)
print(c.execute("select count(*) from sessions").fetchone()[0], c.execute("select count(*) from messages where role='user'").fetchone()[0],
      c.execute("select count(*) from messages where role='user' and content not like ?", ("%" + sys.argv[2] + "%",)).fetchone()[0])
PY
)
ok live-store '[[ $live == "1 3 0" ]]' "sessions/user rows/non-canary user rows = $live"
echo "canary files now: $(grep -rlaF "$CAN" $HH $B /var/lib/hermes-forget /run/hermes-forget 2>/dev/null | paste -sd' ')"
echo "namespace journal canary hits: $(journalctl --namespace=hermes-gateway-dev -o cat --no-pager | grep -c "$CAN")"
dr5
parity
echo "S6_PASS"
