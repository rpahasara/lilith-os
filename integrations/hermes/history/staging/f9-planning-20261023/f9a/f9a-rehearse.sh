#!/usr/bin/env bash
# F9-A LOCAL WSL MIRROR rehearsal (refused on lilith-dev-01). Synthetic Groq only; no real provider, no DEV/PROD.
# Proves D-1 (B) + D-2 behaviourally on the real Hermes runtime of candidate f293e72-f9a1:
#   NEG  the F9-A tests FAIL on the F8r4 tree (they detect the old behaviour);
#   G-4  F7 suite (incl. the rewritten no-preview test) + F9-A tests on the installed release;
#   E1   first-ever message on a FRESH store: no sidecar note stored (api_content NULL) and the provider received
#        exactly [user(raw text)] (request-structure method from the F8r4 continuity work);
#   E2   re-arm: empty the session store (as a FORGET would), first message again -> still no note;
#   E3   unmodified Phase B smoke 35/35 (Router V2 shadow decisions still produced) after a MIRROR-ONLY ledger RESET;
#   E4   decisions log: non-content metadata only, no message text anywhere in it;
#   then G-8, G-9 parity + DR-5, rollback and teardown to the mirror baseline.
set -uo pipefail
[[ $(hostname) != lilith-dev-01 ]] || { echo "refused on lilith-dev-01"; exit 1; }
W=/root/f9a; REL=f293e72-f9a1; PKGN=hermes-gateway-dev-$REL; P=/var/tmp/f8/$PKGN; F8P=/root/f8r4/build/pkg
HH=/home/lilith/.hermes-dev; R=/opt/hermes-gateway-dev/current; SY=/root/f8r4/synth; B=/var/backups/hermes-gateway-dev
L=/var/lib/private/hermes-provider-gate-dev/ledger.log; DEC=$HH/logs/lilith-router-decisions.log
MARK=F8R3-SYNTHETIC-PROVIDER-REPLY; RES=$W/f9a-rehearsal.tsv; : > $RES; EV=$W/ev; rm -rf $EV; mkdir -p $EV
rec() { printf '%s\t%s\t%s\n' "$1" "$2" "$3" | tee -a "$RES"; }
chat() { local c; c=$(grep -c '"path": "/openai/v1/chat/completions"' $SY/requests.jsonl 2>/dev/null); echo "${c:-0}"; }
TOK() { grep '^LILITH_OS_TOKEN=' $HH/.env | cut -d= -f2; }
turn() { curl -s -m 150 -o $EV/turn.json -w '%{http_code}' -H "X-LILITH-OS-Token: $(TOK)" -H 'Content-Type: application/json' \
          -d "{\"message\":\"$1\",\"session\":\"$2\"}" http://127.0.0.1:9901/; }
reply() { python3 -c 'import json;d=json.load(open("'$EV'/turn.json"));print(d.get("state"),"|",(d.get("reply") or "")[:80])'; }
start_ready() {  # readiness of THIS start only: gate START since now + Hermes ready line after the current log end
  local since n0; since=$(date '+%Y-%m-%d %H:%M:%S'); n0=$(cat $HH/logs/gateway.log 2>/dev/null | wc -l)
  systemctl start hermes-gateway-dev
  for _ in $(seq 1 90); do
    ss -Hltn 'sport = :9901' | grep -q . && ss -Hltn 'sport = :9911' | grep -q . \
      && journalctl --namespace=hermes-gateway-dev -u hermes-provider-gate-dev --since "$since" -o cat --no-pager | grep -q '"decision": "START"' \
      && tail -n +$(( n0 + 1 )) $HH/logs/gateway.log 2>/dev/null | grep -q 'Press Ctrl+C to stop' && return 0
    sleep 1; done; return 1; }
# Mirror-only inspector of Hermes state (synthetic data): private copy, never the live files.
STATECHK=$(cat <<'PY'
import hashlib, json, shutil, sqlite3, sys, tempfile
from pathlib import Path
hh, chat_id, raw, reqfile, nth = Path(sys.argv[1]), sys.argv[2], sys.argv[3], sys.argv[4], int(sys.argv[5])
t = Path(tempfile.mkdtemp())
for s in ("state.db", "state.db-wal"):
    if (hh / s).exists(): shutil.copyfile(hh / s, t / s)
c = sqlite3.connect(str(t / "state.db"))
sess = [r[0] for r in c.execute("select id from sessions where chat_id=?", (chat_id,))]
rows = c.execute("select role, content, api_content from messages where session_id=? order by id", (sess[0],)).fetchall() if sess else []
any_api = c.execute("select count(*) from messages where api_content is not null").fetchone()[0]
c.close(); shutil.rmtree(t)
h = lambda x: hashlib.sha256(x.encode()).hexdigest()[:16]
users = [r for r in rows if r[0] == "user"]
reqs = [json.loads(l) for l in open(reqfile) if '"/openai/v1/chat/completions"' in l]
conv = [(m["role"], m["sha"]) for m in reqs[nth - 1].get("msgs", []) if m["role"] in ("user", "assistant")]
ok = (len(sess) == 1 and len(users) == 1 and users[0][1] == raw and users[0][2] is None and any_api == 0
      and conv == [("user", h(raw))])
print(f"sessions={len(sess)} user_msgs={len(users)} content_exact={bool(users) and users[0][1] == raw} "
      f"api_content_null={bool(users) and users[0][2] is None} rows_with_api_content={any_api} "
      f"provider_request#{nth}_conversational={conv} expected=[('user', '{h(raw)}')]")
print("FIRST_CONTACT_CLEAN" if ok else "FIRST_CONTACT_NOT_CLEAN"); sys.exit(0 if ok else 1)
PY
)

echo "#### S0 mirror baseline"
MIRROR_SET_UP=0
if [[ ! -f /etc/systemd/system/lilith-memory-broker.service ]]; then
  bash /root/f8r2/mirror/mirror_setup.sh /root/f8r2/repo /root/f8hd/build/pkg/uv/uv > $EV/mirror-setup.log 2>&1 \
    && MIRROR_SET_UP=1 && rec mirror-setup PASS "stand-ins up" || { rec mirror-setup FAIL "$(tail -3 $EV/mirror-setup.log)"; exit 1; }
fi
for rb in /var/tmp/f8/*/bin/rollback.sh; do [[ -x $rb ]] && bash $rb remove >/dev/null 2>&1; done
systemctl daemon-reload
[[ -d $B ]] && mkdir -p $W/old && mv $B $W/old/backups-$(date +%s)
python3 -I /root/f8r4/amend/patch_fake_groq.py /root/f8r4/mirror/fake_groq.py >/dev/null
python3 -I /root/f8r4/amend/patch_fake_groq_msgs.py /root/f8r4/mirror/fake_groq.py >/dev/null
bash /root/f8r4/mirror/synthprov.sh up >/dev/null
rm -rf /var/tmp/f8 && install -d -m 0700 /var/tmp/f8 && cp $W/out/$PKGN.tar.gz* /var/tmp/f8/
(cd /var/tmp/f8 && sha256sum -c $PKGN.tar.gz.sha256 >/dev/null && tar -xzf $PKGN.tar.gz && cd $PKGN && sha256sum --quiet -c MANIFEST.sha256) \
  && rec G-2 PASS "f9a1 $(cut -c1-16 /var/tmp/f8/$PKGN.tar.gz.sha256) + MANIFEST" || { rec G-2 FAIL ""; exit 1; }
systemctl start lilith-memory-broker.service lilith-authority-dev.service lilith-recovery-witness.service lilith-os-api-dev.service; sleep 4
bash $P/bin/observe_host.sh $EV/M0 >/dev/null
bash $P/bin/dr5_check.sh $EV/dr5-M0.txt > $EV/dr5-M0-check.txt && rec M0-DR5 PASS "$(tail -1 $EV/dr5-M0-check.txt | cut -c1-40)" || { rec M0-DR5 FAIL ""; exit 1; }

echo "#### install candidate (G-1, G-3, G-4: F7 + F9-A suites, NEG control)"
bash $P/bin/backup_pre_install.sh >/dev/null; PRE=$(ls -d $B/pre-* | tail -1)
F8_SIM=1 bash $P/bin/install.sh > $EV/install.log 2>&1 && grep -q "F8_INSTALL_STAGED $REL" $EV/install.log && rec G-3 PASS staged || { rec G-3 FAIL "$(tail -2 $EV/install.log)"; exit 1; }
bash $P/bin/dr5_check.sh $EV/dr5-installed.txt > $EV/dr5-i.txt && rec G-3b PASS "$(tail -1 $EV/dr5-i.txt | cut -c1-40)" || rec G-3b FAIL ""
suite() {  # <tag> <src dir> <home dir> <dev config> -> runs F7 + F9-A suites as lilith in a G-4 layout
  local T; T=$(mktemp -d /var/tmp/f9a-g4-XXXXXX)
  # the installed release is world-readable; the F8r4 build tree under /root is not, so it is copied for uid lilith
  if [[ $2 == /root/* ]]; then cp -a "$2" $T/hermes-agent; else ln -s "$2" $T/hermes-agent; fi
  mkdir $T/hermes-home-dev $T/tests
  cp -a "$3/lilith_router" "$3/plugins" $T/hermes-home-dev/
  cp $P/tests/f7-home/config.yaml $T/hermes-home-dev/; cp $P/tests/f7-home/router.yaml $T/hermes-home-dev/lilith_router/
  cp $P/tests/test_f7_offline.py $P/tests/test_f9a_offline.py $T/tests/; cp "$4" $T/dev-config.yaml
  chown -R lilith:lilith $T; chmod 700 $T
  runuser -u lilith -- env -i PATH=/usr/bin:/bin HOME=$T PYTHONUNBUFFERED=1 $R/venv/bin/python -B $T/tests/test_f7_offline.py > $EV/$1-f7.log 2>&1
  runuser -u lilith -- env -i PATH=/usr/bin:/bin HOME=$T PYTHONUNBUFFERED=1 F9A_DEV_CONFIG=$T/dev-config.yaml $R/venv/bin/python -B $T/tests/test_f9a_offline.py > $EV/$1-f9a.log 2>&1
  rm -rf -- "$T"; }
suite G4 $R/src $P/home $P/home/config.yaml
grep -q '^OK$' $EV/G4-f7.log && rec G-4-F7 PASS "$(grep '^Ran ' $EV/G4-f7.log) OK" || rec G-4-F7 FAIL "$(grep -E '^(FAIL|ERROR):|^Ran |^FAILED' $EV/G4-f7.log | tr '\n' ' ' | cut -c1-300)"
grep -q '^OK$' $EV/G4-f9a.log && rec G-4-F9A PASS "$(grep '^Ran ' $EV/G4-f9a.log) OK" || rec G-4-F9A FAIL "$(grep -E '^(FAIL|ERROR):|^Ran |^FAILED' $EV/G4-f9a.log | tr '\n' ' ' | cut -c1-300)"
suite NEG $F8P/src $F8P/home $F8P/home/config.yaml
neg=$(grep -E '^(FAIL|ERROR):' $EV/NEG-f9a.log | sed 's/^[A-Z]*: //; s/ (.*//' | sort | paste -sd' ')
want="test_all_eight_writers_log_no_message_text test_dev_config_disables_profile_build test_empty_and_none_message test_event_ids_are_random_not_content_derived test_run_py_skips_first_contact_note_for_lilith_os test_source_has_no_preview_key_and_no_text_hashing"
grep -q 'PermissionError' $EV/NEG-f9a.log && rec NEG-control INVALID "environment error in the negative control"
[[ $neg == "$want" ]] && rec NEG-control DETECTED "on F8r4 exactly the 6 behaviour tests fail; persona/upstream/YAML-trap tests pass: $neg" \
  || rec NEG-control UNEXPECTED "failing on F8r4: [$neg]"
grep -qE '^(FAIL|ERROR): test_shadow_mode' $EV/NEG-f7.log && rec NEG-control-F7 DETECTED "rewritten F7 no-preview test fails on F8r4 router" || rec NEG-control-F7 INFO "$(grep -E '^Ran |^OK|^FAILED' $EV/NEG-f7.log | tr '\n' ' ')"

echo "#### G-5, G-6, G-6b"
bash $P/bin/provision_console_token.sh >/dev/null
printf '%s\n' "$(cat $SY/synthetic-key)" | script -qec "bash $P/bin/provision_provider_key.sh" /dev/null > $EV/key.log 2>&1
$R/venv/bin/python -I -B $R/bin/verify_release.py --full > $EV/g5c.log 2>&1 && rec G-5c PASS "$(tail -1 $EV/g5c.log)" || { rec G-5c FAIL "$(tail -3 $EV/g5c.log)"; exit 1; }
start_ready && rec G-6 PASS "ready" || { rec G-6 FAIL ""; exit 1; }
bash $R/bin/sandbox_probe.sh > $EV/probe.txt 2>&1 && rec G-6b-sandbox PASS "$(tail -1 $EV/probe.txt)" || rec G-6b-sandbox FAIL "$(grep FAIL $EV/probe.txt | tr '\n' ' ')"
bash $R/bin/gate_probe.sh > $EV/gprobe.txt 2>&1 && rec G-6b-gate PASS "$(tail -1 $EV/gprobe.txt)" || rec G-6b-gate FAIL ""

echo "#### E1 first-ever message on a fresh store"
E1="F9A-CANARY-7Q2X first-ever message: reply with one short sentence."
c=$(turn "$E1" f9a-e1); r=$(reply); [[ $c == 200 && $r == completed* && $r == *$MARK* ]] && rec E1-turn PASS "$c $r" || rec E1-turn FAIL "$c $r"
bash $R/bin/rollback.sh stop > $EV/e1-stop.log 2>&1
python3 -c "$STATECHK" $HH f9a-e1 "$E1" $SY/requests.jsonl 1 > $EV/e1-state.txt 2>&1 \
  && rec E1-no-sidecar PASS "$(head -1 $EV/e1-state.txt | cut -c1-300)" || rec E1-no-sidecar FAIL "$(cat $EV/e1-state.txt | tr '\n' ' ' | cut -c1-300)"

echo "#### E2 re-arm: empty the session store (as a FORGET would), first message again"
runuser -u lilith -- python3 -c 'import sqlite3,sys; c=sqlite3.connect(sys.argv[1]); c.execute("delete from messages"); c.execute("delete from sessions"); c.commit(); print(c.execute("select count(*) from sessions").fetchone()[0], c.execute("select count(*) from messages").fetchone()[0]); c.close()' $HH/state.db > $EV/e2-empty.txt 2>&1
[[ $(cat $EV/e2-empty.txt) == "0 0" ]] && rec E2-store-empty PASS "sessions=0 messages=0 (has_any_sessions false)" || rec E2-store-empty FAIL "$(cat $EV/e2-empty.txt)"
start_ready || { rec E2-start FAIL ""; exit 1; }
E2="F9A-CANARY-7Q2X message after an emptied store: one short sentence."
c=$(turn "$E2" f9a-e2); r=$(reply); [[ $c == 200 && $r == completed* && $r == *$MARK* ]] && rec E2-turn PASS "$c $r" || rec E2-turn FAIL "$c $r"
bash $R/bin/rollback.sh stop > $EV/e2-stop.log 2>&1
python3 -c "$STATECHK" $HH f9a-e2 "$E2" $SY/requests.jsonl 2 > $EV/e2-state.txt 2>&1 \
  && rec E2-no-rearm PASS "$(head -1 $EV/e2-state.txt | cut -c1-300)" || rec E2-no-rearm FAIL "$(cat $EV/e2-state.txt | tr '\n' ' ' | cut -c1-300)"

echo "#### E3 unmodified Phase B smoke (MIRROR-ONLY synthetic ledger RESET; the DEV budget is never reset)"
start_ready || { rec E3-start FAIL ""; exit 1; }
bash $R/bin/gate_budget.sh reset --owner-approved mirror-only-f9a-smoke > $EV/mirror-reset.txt 2>&1
rec mirror-ledger-reset INFO "WSL mirror synthetic ledger only: $(cat $EV/mirror-reset.txt | cut -c1-120)"
f0=$(chat)
$R/venv/bin/python -I -B $R/bin/smoke_console.py --phase B --core-api --expect-marker $MARK > $EV/smoke.txt 2>&1 \
  && rec E3-smoke PASS "$(tail -1 $EV/smoke.txt); provider +$(( $(chat) - f0 ))" || rec E3-smoke FAIL "$(grep -E '^FAIL|F8_SMOKE' $EV/smoke.txt | tr '\n' ' ' | cut -c1-400)"

echo "#### E4 decisions log content"
python3 - $DEC > $EV/e4.txt <<'PY'
import json, re, sys
raw = open(sys.argv[1], encoding="utf-8").read(); recs = [json.loads(l) for l in raw.splitlines()]
bad = [r for r in recs if "preview" in r or not re.fullmatch(r"[0-9a-f]{32}", r.get("event_id", "")) or "msg_chars" not in r]
text = [t for t in ("F9A-CANARY", "F8-SYNTHETIC", "synthetic", "turn 1", "kubernetes") if t in raw]
ids = [r["event_id"] for r in recs if "event_id" in r]
print(f"records={len(recs)} bad={len(bad)} text_found={text} unique_event_ids={len(set(ids)) == len(ids)} "
      f"chats={sorted({r.get('chat_id') for r in recs})} live_any={any(r.get('live') for r in recs)}")
sys.exit(0 if recs and not bad and not text and len(set(ids)) == len(ids) and not any(r.get("live") for r in recs) else 1)
PY
[[ $? -eq 0 ]] && rec E4-decisions PASS "$(cat $EV/e4.txt)" || rec E4-decisions FAIL "$(cat $EV/e4.txt)"
rec D4-observation INFO "canary occurrences outside the decisions log (D-4/F9-B scope): gateway.log=$(grep -c 'F9A-CANARY' $HH/logs/gateway.log 2>/dev/null) agent.log=$(grep -c 'F9A-CANARY' $HH/logs/agent.log 2>/dev/null) journal=$(journalctl --namespace=hermes-gateway-dev -o cat --no-pager | grep -c 'F9A-CANARY')"
rec SOUL INFO "HERMES_HOME SOUL.md (runtime-created by Hermes, not shipped): $([[ -f $HH/SOUL.md ]] && sha256sum < $HH/SOUL.md | cut -c1-16 || echo absent)"

echo "#### G-8 + G-9"
systemctl start hermes-gateway-dev-retention.service; [[ $(systemctl show hermes-gateway-dev-retention.service -p Result --value) == success ]] && rec G-8 PASS retention || rec G-8 FAIL ""
bash $P/bin/observe_host.sh $EV/g9 >/dev/null
bash $P/bin/compare_observations.sh $PRE/observation $EV/g9 > $EV/g9-cmp.txt && rec G-9-obs PASS "$(tail -1 $EV/g9-cmp.txt)" || rec G-9-obs FAIL "$(grep DIFF $EV/g9-cmp.txt | tr '\n' ' ')"
bash $P/bin/dr5_check.sh $EV/dr5-g9.txt > $EV/dr5-g9-check.txt && rec G-9-DR5 PASS "$(tail -1 $EV/dr5-g9-check.txt | cut -c1-40)" || rec G-9-DR5 FAIL ""

echo "#### cleanup to the mirror baseline"
bash $R/bin/rollback.sh stop >/dev/null 2>&1; bash $P/bin/rollback.sh remove > $EV/r2.log 2>&1
systemctl daemon-reload; bash $P/bin/observe_host.sh $EV/final >/dev/null
bash $P/bin/compare_observations.sh $EV/M0 $EV/final > $EV/final-cmp.txt && [[ $(ls -A $HH) == memories ]] && rec FINAL CLEAN "M0 == FINAL, HH=memories" || rec FINAL NOT_CLEAN "$(grep DIFF $EV/final-cmp.txt | tr '\n' ' ')"
bash /root/f8r4/mirror/synthprov.sh down >/dev/null
[[ $MIRROR_SET_UP == 1 ]] && { bash /root/f8r2/mirror/mirror_teardown.sh > $EV/mirror-teardown.log 2>&1; rec mirror-teardown INFO "$(tail -1 $EV/mirror-teardown.log)"; }
echo; echo "TOTAL: $(grep -cP '\t(PASS|CLEAN|DETECTED|INFO)\t' $RES) ok / $(wc -l < $RES) rows; NOT ok: $(grep -cvP '\t(PASS|CLEAN|DETECTED|INFO)\t' $RES)"
