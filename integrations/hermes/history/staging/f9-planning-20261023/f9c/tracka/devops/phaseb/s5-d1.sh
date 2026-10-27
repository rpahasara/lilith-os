STEP=s5-d1
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
# S5 (D-1): data-scope inventory of what the FORGET will erase, then 3 fixed synthetic canary turns (no provider).
LED0=68b4057ef39c7f99d0fc51b26b704bfd936671894a7d523a0952be98d0562e54
gatej() { journalctl --namespace=hermes-gateway-dev -u hermes-provider-gate-dev -o cat --no-pager 2>/dev/null; }
echo "--- scope: conversation-bearing backup items (what the Hermes owner's BACKUPS phase will erase)"
$R/python/cpython-3.11.16-linux-x86_64-gnu/bin/python3.11 -I -B - "$R/bin" "$B" <<'PY'
import collections, sys
sys.path.insert(0, sys.argv[1]); import hermes_forget_executor as X
items = X.scan_backups(X.Path(sys.argv[2]))
c = collections.Counter((str(i.path.relative_to(sys.argv[2])).split("/")[0], i.kind) for i in items)
for (top, kind), n in sorted(c.items()): print(f"  {top} {kind} x{n}")
print(f"  total={len(items)}")
PY
echo "--- scope: live Hermes store before the turns"
python3 - "$HH/state.db" <<'PY'
import sqlite3, sys, os
p = sys.argv[1]
if not os.path.exists(p): print("  state.db absent (fresh store)"); raise SystemExit
c = sqlite3.connect("file:" + p + "?mode=ro", uri=True)
print("  sessions", c.execute("select count(*) from sessions").fetchone()[0], "messages", c.execute("select count(*) from messages").fetchone()[0])
PY
F0=$(gatej | grep -c '"decision": "FORWARDED"'); K0=$(gatej | grep -c '"reason": "KEY_NOT_PROVISIONED"')
codes=""
for i in 1 2 3; do
  c=$(curl -s -m 170 -o $RUN/d1-turn$i.json -w '%{http_code}' -H 'Content-Type: application/json' \
      -d "{\"message\":\"$CAN-$i synthetic drill turn; no personal data.\",\"session\":\"f9c2-dev-drill\"}" http://127.0.0.1:8765/os/conversation)
  codes="$codes$c/"
done
echo "turn http codes: $codes  last state: $(python3 -c 'import json,sys;d=json.load(open(sys.argv[1]));print(d.get("state"))' $RUN/d1-turn3.json)"
ok d1-http '[[ $codes == "200/200/200/" ]]'
sleep 2
F1=$(gatej | grep -c '"decision": "FORWARDED"'); K1=$(gatej | grep -c '"reason": "KEY_NOT_PROVISIONED"'); PR=$(gatej | grep -c '"reason": "PATH_NOT_ALLOWED"')
ok d1-no-forward '[[ $F0 -eq 0 && $F1 -eq 0 ]]' "FORWARDED total=$F1"
ok d1-key-refusals '[[ $((K1 - K0)) -eq 3 ]]' "KEY_NOT_PROVISIONED +$((K1 - K0)); local metadata probes PATH_NOT_ALLOWED=$PR"
ok d1-ledger '[[ $(sha256sum < $LED | cut -c1-64) == $LED0 ]]' "ledger byte-identical"
hz=$(bash $R/bin/gate_budget.sh show); ok d1-still-exhausted '[[ $hz == *"\"budget_used\": 5"* && $hz == *"\"key_loaded\": false"* ]]'
rows=$(python3 - "$HH/state.db" "$CAN" <<'PY'
import sqlite3, sys
c = sqlite3.connect("file:" + sys.argv[1] + "?mode=ro", uri=True)
r = dict(c.execute("select m.role, count(*) from messages m where m.content like ? group by m.role", ("%" + sys.argv[2] + "%",)).fetchall())
print(r.get("user", 0), "sessions=%d" % c.execute("select count(*) from sessions").fetchone()[0],
      "sources=%s" % sorted({x[0] for x in c.execute("select source from sessions")}),
      "users=%d" % c.execute("select count(distinct user_id) from sessions").fetchone()[0])
PY
)
echo "state.db: canary user rows=$rows"
ok d1-state-db '[[ $rows == "3 sessions=1 sources=['"'"'lilith_os'"'"'] users=1" ]]'
parity
echo "S5_PASS"
