STEP=s7-d2
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
# S7 (D-2 + D-3): the ONE governed synthetic FORGET with REF owner-g0-f9c2-drill-20261025, then the D-3 checks.
# The work runs in a detached worker (setsid) so an SSH/plink drop cannot interrupt the FORGET; this launcher only
# follows its output. NO systemctl start of the gateway while held: the hold and executor units declare
# Conflicts=hermes-gateway-dev, so a start job would stop them (start refusal is proven from its inputs instead).
REF=owner-g0-f9c2-drill-20261025
W=$RUN/s7-worker.sh; WO=$RUN/s7-worker.out
[[ -e $W || -e $WO ]] && die "worker already exists: no second FORGET attempt"
{ declare -p STEP RUN CORE HH B R CORE_SHA LED INTENT MARK CAN REF; declare -f die ok pids parity dr5; cat <<'WORKER'
set -uo pipefail
LED0=68b4057ef39c7f99d0fc51b26b704bfd936671894a7d523a0952be98d0562e54
PY=$R/python/cpython-3.11.16-linux-x86_64-gnu/bin/python3.11
RD=/var/lib/hermes-forget/receipts; EL=/var/lib/hermes-forget/epochs/epochs.log
drill() { runuser -u lilith -- env -C /tmp HOME=/tmp $CORE/api-venv/bin/python -I -B $R/bin/f9c_dev_drill.py --core-api $CORE/current "$@" 2>&1; }
gw() { echo "$(systemctl is-active hermes-gateway-dev) cond=$(systemctl show hermes-gateway-dev -p ConditionResult --value)"; }
port() { ss -Hltn "sport = :$1" | grep -q . && echo open || echo closed; }
echo "=== worker $(date -u +%FT%TZ) pid=$$"
API0=$(systemctl show lilith-os-api-dev -p MainPID --value); GATE0=$(systemctl show hermes-provider-gate-dev -p MainPID --value)
echo "pre: api=$API0 gate=$GATE0 gateway=$(systemctl show hermes-gateway-dev -p MainPID --value) $(gw)"
[[ ! -e $INTENT && ! -e $MARK && ! -s $EL ]] || die "pre-state changed"
echo "--- D-2 forget (REF=$REF)"
drill --owner-approval $REF forget > $RUN/d2-forget.json &
CP=$!
held=0
for _ in $(seq 1 900); do [[ $(stat -c %U $INTENT 2>/dev/null) == root && $(systemctl is-active hermes-gateway-dev) != active ]] && { held=1; break; }; sleep 0.2; done
if [[ $held == 1 ]]; then
  st=$(stat -c '%U:%G %a' $INTENT)
  c=$(curl -s -m 30 -o $RUN/d2-held.json -w '%{http_code}' -H 'Content-Type: application/json' \
      -d "{\"message\":\"$CAN-held synthetic hold probe; no personal data.\",\"session\":\"f9c2-dev-drill\"}" http://127.0.0.1:8765/os/conversation)
  d=$(python3 -c 'import json,sys;d=json.load(open(sys.argv[1]));print(d.get("detail") or d.get("state") or "")' $RUN/d2-held.json 2>/dev/null)
  runuser -u lilith -- rm -f $INTENT 2>/dev/null; still=$([[ -e $INTENT ]] && echo kept || echo gone)
  dropin=$(systemctl show hermes-gateway-dev -p DropInPaths --value | tr ' ' '\n' | grep -c hermes-gateway-dev.service.d)
  conds=$(systemctl show hermes-gateway-dev -p ConditionPathExists,ConditionPathExistsGlob 2>/dev/null | paste -sd' ')
  echo "held: intent=[$st] relay=$c/$d gateway=[$(gw)] port9901=$(port 9901) lilith-rm=$still dropins=$dropin marker=$([[ -e $MARK ]] && echo present || echo absent-yet)"
  ok d2-held '[[ $st == "root:lilith-forget 640" && $c == 503 && $d == FORGET_HOLD_ACTIVE && $(systemctl is-active hermes-gateway-dev) != active && $(port 9901) == closed && $still == kept && $dropin -ge 1 ]]' "hold-first enforced; gateway isolated"
else echo "STEP_FAIL d2-held hold never observed (FORGET continues; no retry)"; fi
wait $CP; rc=$?
echo "forget rc=$rc: $(tr -s ' \n' ' ' < $RUN/d2-forget.json | cut -c1-900)"
ok d2-complete 'grep -q "\"status\": \"COMPLETE\"" $RUN/d2-forget.json'
OW=$(python3 - $RUN/d2-forget.json <<'PY'
import json, sys
t = open(sys.argv[1]).read(); d, _ = json.JSONDecoder().raw_decode(t[t.index("{"):])
print("OWNERS_OK" if sorted(d.get("completedOwners") or []) == ["HERMES_DEV_CONVERSATION", "L04", "L18_V2"] and not d.get("pendingOwners") else "OWNERS_BAD", d.get("completedOwners"), d.get("pendingOwners"))
PY
)
ok d2-owners '[[ $OW == OWNERS_OK* ]]' "$OW"
for _ in $(seq 1 180); do [[ ! -e $INTENT && ! -e $MARK && $(port 9901) == open ]] && break; sleep 1; done
ok d3-release '[[ ! -e $INTENT && ! -e $MARK && $(port 9901) == open && $(systemctl is-active hermes-gateway-dev) == active ]]' "$(gw)"
echo "F9-C unit event order:"; journalctl -u hermes-forget-hold -u hermes-forget-executor -u hermes-forget-restart -u hermes-forget-reconcile -o short-iso-precise --since -30min --no-pager | sed -n 's/^\([^ ]*\) [^ ]* \([^ []*\).*"event": "\([A-Z_]*\)".*/  \1 \2 \3/p'
echo "--- D-3 receipt / epoch"
ok d3-one-receipt '[[ $(find $RD -type f | wc -l) -eq 1 ]]' "$(find $RD -type f -printf '%f %u:%g %m\n')"
RC=$(find $RD -type f | head -1)
ok d3-receipt-mode '[[ $(stat -c "%U:%G %a" "$RC") == "root:lilith-forget 640" ]]'
RO=$($PY -I -B - "$R/bin" "$RC" "$REF" <<'PY'
import sys, json
sys.path.insert(0, sys.argv[1]); import hermes_forget_executor as X
r = json.load(open(sys.argv[2]))
ok = (r.get("status") == "COMPLETE" and r.get("claim") == "LOGICAL_ERASURE_VERIFIED" and r.get("providerErasure") == "ATTESTED_ZDR_NOT_VERIFIED"
      and r.get("erasureEpoch") == 1 and all(r.get("checks", {}).values()) and len(r.get("checks", {})) == len(X.CHECKS)
      and r.get("receiptDigest") == X.receipt_digest(r))
print("receipt:", {k: r.get(k) for k in ("status", "claim", "providerErasure", "erasureEpoch", "scope")}, "phases", r.get("phases"),
      "checks", r.get("checks"), "digest", str(r.get("receiptDigest"))[:16], "RECEIPT_OK" if ok else "RECEIPT_BAD")
PY
)
echo "$RO"; ok d3-receipt '[[ $RO == *RECEIPT_OK ]]'
ok d3-epoch '[[ $(wc -l < $EL) -eq 1 && $(grep -c "\"epoch\": 1" $EL) -eq 1 ]]'
s=$(drill status); echo "status: $s"
ok d3-status '[[ $s == *"\"completed\": true"* && $s == *"\"inFlight\": false"* && $s == *"\"intent\": \"ABSENT\""* ]]'
echo "--- D-3 erasure"
hits=$(grep -rlaF "$CAN" $HH $B /var/lib/hermes-forget /run/hermes-forget 2>/dev/null | paste -sd' ')
ok d3-canary-files '[[ -z $hits ]]' "hits=[${hits}]"
jn=$(journalctl --namespace=hermes-gateway-dev -o cat --no-pager | grep -c "$CAN"); ok d3-canary-journal '[[ $jn -eq 0 ]]'
inv=$($PY -I -B -c 'import sys;sys.path.insert(0,sys.argv[1]);import hermes_forget_executor as X;print(len(X.scan_backups(X.Path(sys.argv[2]))))' "$R/bin" "$B")
ok d3-backups-clean '[[ $inv == 0 ]]' "scan_backups items=$inv"
tomb=$(python3 -c 'import json,glob,collections;f=glob.glob("/var/backups/hermes-gateway-dev/FORGET-TOMBSTONES/*.json");e=[x for p in f for x in json.load(open(p))["removed"]];print(len(f),len(e),dict(collections.Counter(x["kind"] for x in e)))')
ok d3-tombstone '[[ $tomb == "1 73 "* ]]' "$tomb"
ls -d $B/rollback-20261023T123157Z $B/upgrade-pre-20261023T123016Z/hermes-dev-home.tar >/dev/null && echo "F8r2 backup dirs kept (non-conversation content retained)"
live=$(python3 - "$HH/state.db" <<'PY'
import sqlite3, sys
c = sqlite3.connect("file:" + sys.argv[1] + "?mode=ro", uri=True)
print(c.execute("select count(*) from sessions").fetchone()[0], c.execute("select count(*) from messages").fetchone()[0])
PY
)
echo "live store after restart: sessions/messages=$live"
ok d3-probe-clean '[[ ! -e $CORE/data/privacy_governance.dev.db && ! -e $CORE/data/cognitive_memory.dev.db && ! -e $CORE/data/canonical-durability-probe ]]'
echo "--- D-3 budget / health / parity"
ok d3-ledger '[[ $(sha256sum < $LED | cut -c1-64) == $LED0 ]]' "ledger byte-identical (no upstream request, no reset)"
hz=$(bash $R/bin/gate_budget.sh show); echo "gate: $hz"
ok d3-budget '[[ $hz == *"\"budget_used\": 5"* && $hz == *"\"key_loaded\": false"* && $hz == *BUDGET_EXHAUSTED* ]]'
ok d3-gate-pid '[[ $(systemctl show hermes-provider-gate-dev -p MainPID --value) == $GATE0 ]]'
v=$($R/venv/bin/python -I -B $R/bin/verify_release.py --full 2>&1 | tail -1); ok d3-verify '[[ $v == *"F8_VERIFY_PASS full f293e72-f9c2"* ]]' "$v"
h=$(curl -s -m 5 http://127.0.0.1:8765/health); ok d3-coreapi '[[ $h == *"\"status\":\"ok\""* && $(systemctl show lilith-os-api-dev -p MainPID --value) == $API0 ]]' "api pid $API0 unchanged"
for u in hermes-forget.path hermes-forget-hold.path hermes-forget-reconcile.timer; do ok "d3-unit-$u" '[[ $(systemctl is-active $u) == active ]]'; done
dr5
parity
echo "S7_PASS"
WORKER
} > $W
chmod 700 $W; bash -n $W || die "worker syntax"
echo "worker sha $(sha256sum < $W | cut -c1-16)"
setsid nohup bash $W > $WO 2>&1 < /dev/null &
for _ in $(seq 1 540); do grep -qE '^(S7_PASS|STEP_FAIL)' $WO 2>/dev/null && ! pgrep -f "bash $W" >/dev/null && break; sleep 1; done
cat $WO
pgrep -f "bash $W" >/dev/null && echo "WORKER_STILL_RUNNING (re-read $WO)"
