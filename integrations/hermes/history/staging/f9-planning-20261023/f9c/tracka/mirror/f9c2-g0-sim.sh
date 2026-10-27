#!/usr/bin/env bash
# MIRROR ONLY (refused on lilith-dev-01): G-0 final safety verification.
#  V2  B-4 preflight: (a) F8r4 with the b9eb32c Core API -> must FAIL, only on coreapi-* checks; (b) wrong expected SHA
#      -> FAIL; (c) stand-in deploy of the reviewed 950fc02 Core API bytes under a release named by the expected SHA
#      -> PASS. Every run: identical host snapshot before/after (read-only).
#  V1  D-1 canary turns: F8r4 budget really exhausted (5/5) -> U-1 preserve -> f9c2 install -> ledger CARRIED forward
#      (copy) -> token, verify, gateway -> 3 canary turns through the Core API relay; proves: canary rows in Hermes
#      state.db, gate refused every provider attempt with KEY_NOT_PROVISIONED, 0 requests reached the (synthetic)
#      upstream, ledger byte-identical (still exhausted); then f9c2 R-2 + restore_f8r4: F8r4 ledger identical.
set -uo pipefail
[[ $(hostname) != lilith-dev-01 ]] || { echo refused; exit 1; }
W=/root/f9ca; T=$W/tracka; P8=/var/tmp/f8/hermes-gateway-dev-f293e72-f8r4; P9=/var/tmp/f8/hermes-gateway-dev-f293e72-f9c2
SY=/root/f8r4/synth; B=/var/backups/hermes-gateway-dev; CORE=/home/lilith/.hermes/lilith-os-dev; HH=/home/lilith/.hermes-dev
LED=/var/lib/private/hermes-provider-gate-dev/ledger.log; CAN=F9C2-G0-CANARY
EV=$W/g0-sim-ev; RES=$W/g0-sim.tsv; : > $RES; rm -rf $EV; mkdir -p $EV
FAKESHA=f9c2f9c2f9c2f9c2f9c2f9c2f9c2f9c2f9c2f9c2
rec() { printf '%s\t%s\t%s\n' "$1" "$2" "$3" | tee -a "$RES"; }
relay() { curl -s -m 170 -o $EV/relay.json -w '%{http_code}' -H 'Content-Type: application/json' \
  -d "{\"message\":\"$1\",\"session\":\"$2\"}" http://127.0.0.1:8765/os/conversation; }
gatej() { journalctl --namespace=hermes-gateway-dev -u hermes-provider-gate-dev -o cat --no-pager 2>/dev/null; }
wait9901() { for _ in $(seq 1 120); do ss -Hltn 'sport = :9901' | grep -q . && ss -Hltn 'sport = :9911' | grep -q . && return 0; sleep 1; done; return 1; }
MIRROR_SET_UP=0; CORE0=""
cleanup() { trap - EXIT
  [[ -x /opt/hermes-gateway-dev/current/bin/rollback.sh ]] && bash /opt/hermes-gateway-dev/current/bin/rollback.sh remove > $EV/cleanup.log 2>&1
  rm -rf $CORE/releases/$FAKESHA
  [[ -n $CORE0 ]] && ln -sfn "$CORE0" $CORE/current.new && chown -h lilith:lilith $CORE/current.new && mv -Tf $CORE/current.new $CORE/current
  systemctl daemon-reload; bash /root/f8r4/mirror/synthprov.sh down >/dev/null
  [[ $MIRROR_SET_UP == 1 ]] && bash /root/f8r2/mirror/mirror_teardown.sh > $EV/teardown.log 2>&1
  echo "TOTAL: $(grep -cP '\t(PASS|INFO)\t' $RES) ok / $(wc -l < $RES) rows; NOT ok: $(grep -cvP '\t(PASS|INFO)\t' $RES)"; }
trap cleanup EXIT
snap() {
  { find /opt/hermes-gateway-dev /etc/hermes-gateway-dev /etc/hermes-provider-gate-dev /var/lib/private/hermes-provider-gate-dev \
         $CORE /etc/systemd/system /etc/tmpfiles.d $B -xdev \( -type f -printf '%p %U %G %m %s %T@\n' \) \
         -o \( ! -type f -printf '%p %y %U %G %m\n' \) 2>/dev/null | LC_ALL=C sort
    find $HH -maxdepth 1 \( -name config.yaml -o -name .env -o -name SOUL.md -o -name lilith_router -o -name plugins \) \
         -printf '%p %U %G %m %s %T@\n' | LC_ALL=C sort
    getent group | LC_ALL=C sort; ls /var/lib | LC_ALL=C sort; } | sha256sum | cut -c1-16; }
b4() {  # <tag> [expected sha] : one preflight run with the read-only proof
  local s0 s1; s0=$(snap)
  F9C2_B4_SIM=1 F9C2_EXPECT_CORE_SHA=${2:-} bash $T/devops/f9c2-b4-preflight.sh > $EV/b4-$1.log 2>&1
  s1=$(snap)
  { [[ $s0 == "$s1" ]] && rec "B-4-$1-read-only" PASS "snapshot identical ($s0)" || rec "B-4-$1-read-only" FAIL "$s0 != $s1"; } >&2
  echo "$(tail -1 $EV/b4-$1.log)|$(grep -E '^CHECK [^ ]+ FAIL' $EV/b4-$1.log | awk '{print $2}' | paste -sd,)"; }

if [[ ! -f /etc/systemd/system/lilith-memory-broker.service ]]; then
  bash /root/f8r2/mirror/mirror_setup.sh /root/f8r2/repo /root/f8hd/build/pkg/uv/uv > $EV/mirror-setup.log 2>&1 && MIRROR_SET_UP=1 \
    || { rec mirror-setup FAIL ""; exit 1; }
fi
CORE0=$(readlink $CORE/current)
[[ -d $B ]] && mkdir -p $W/old && mv $B $W/old/backups-$(date +%s)
python3 -I /root/f8r4/amend/patch_fake_groq.py /root/f8r4/mirror/fake_groq.py >/dev/null
python3 -I /root/f8r4/amend/patch_fake_groq_msgs.py /root/f8r4/mirror/fake_groq.py >/dev/null
bash /root/f8r4/mirror/synthprov.sh up >/dev/null
rm -rf /var/tmp/f8 && install -d -m 0700 /var/tmp/f8
cp /root/f8r4/out/hermes-gateway-dev-f293e72-f8r4.tar.gz* $W/out-f9c2/hermes-gateway-dev-f293e72-f9c2.tar.gz* /var/tmp/f8/
(cd /var/tmp/f8 && sha256sum -c --quiet *.sha256 && for t in *.tar.gz; do tar -xzf $t; done) || { rec G-2 FAIL ""; exit 1; }
[[ $(cut -c1-64 /var/tmp/f8/hermes-gateway-dev-f293e72-f9c2.tar.gz.sha256) == 4b0b0110dde1cccd585203ea9a92cfe8b8cbe31d8e1a6e4edb461ba2c09c3ba5 ]] \
  && rec f9c2-package PASS "4b0b0110… unchanged" || { rec f9c2-package FAIL ""; exit 1; }
systemctl start lilith-memory-broker.service lilith-authority-dev.service lilith-recovery-witness.service lilith-os-api-dev.service; sleep 4

echo "#### F8r4 as on DEV: installed, key provisioned, budget EXHAUSTED by real turns"
bash $P8/bin/backup_pre_install.sh >/dev/null
F8_SIM=1 bash $P8/bin/install.sh > $EV/f8r4-install.log 2>&1 || { rec F8R4-install FAIL "$(tail -2 $EV/f8r4-install.log)"; exit 1; }
bash $P8/bin/provision_console_token.sh >/dev/null
printf '%s\n' "$(cat $SY/synthetic-key)" | script -qec "bash $P8/bin/provision_provider_key.sh" /dev/null > $EV/key.log 2>&1
systemctl start hermes-gateway-dev; wait9901 || { rec F8R4-start FAIL ""; exit 1; }
sleep 3; codes=""; for i in 1 2 3 4 5 6; do codes="$codes$(relay "F8r4 budget turn $i, reply briefly." f9c2-g0-f8r4)/"; done
hz=$(bash /opt/hermes-gateway-dev/current/bin/gate_budget.sh show)
echo "$hz" | grep -q '"budget_used": 5' && echo "$hz" | grep -q '"available": false' \
  && rec F8R4-exhausted PASS "6 turns: http=[$codes] healthz=${hz:0:160}" || rec F8R4-exhausted FAIL "${hz:0:200}"
for _ in $(seq 1 30); do [[ $(systemctl list-jobs --no-legend | wc -l) -eq 0 ]] && break; sleep 2; done

echo "#### V2 B-4: (a) F8r4 + b9eb32c Core API (today's DEV) -> must FAIL only on the Core API checks"
o=$(b4 a); rec B-4-a INFO "$o"
fl=$(echo "$o" | cut -d'|' -f2 | tr ',' '\n' | grep -v '^coreapi-' | paste -sd,)
[[ $o == "F9C2_B4 FAIL"* && -z $fl && $o == *coreapi-expected-sha-given* && $o == *coreapi-f9c-privacy_forget_intent.py* ]] \
  && rec B-4-a-failclosed PASS "undeployed F9-C refused; no non-Core-API check failed" || rec B-4-a-failclosed FAIL "other fails: [$fl]"
echo "#### (b)+(c) stand-in deploy of the reviewed 950fc02 Core API bytes as release $FAKESHA"
NEW=$CORE/releases/$FAKESHA; mkdir -p $NEW/lilith_memory
cp $W/repo/services/core-api/app.py $W/repo/services/core-api/requirements.txt $NEW/; cp $W/repo/services/core-api/lilith_memory/*.py $NEW/lilith_memory/
echo "$FAKESHA-bundle" > $NEW/.bundle-sha256; chown -R lilith:lilith $NEW
ln -sfn $NEW $CORE/current.new && chown -h lilith:lilith $CORE/current.new && mv -Tf $CORE/current.new $CORE/current
o=$(b4 b 0000000000000000000000000000000000000000); rec B-4-b INFO "$o"
[[ $o == "F9C2_B4 FAIL"* && $o == *coreapi-release-is-expected* ]] && rec B-4-b-wrong-sha PASS "a release that is not the expected commit is refused" || rec B-4-b-wrong-sha FAIL ""
o=$(b4 c $FAKESHA); rec B-4-c INFO "$o"
[[ $o == "F9C2_B4 PASS|" ]] && rec B-4-c-pass PASS "$(grep -c '^CHECK' $EV/b4-c.log) checks, all required PASS with the reviewed bytes deployed" || rec B-4-c-pass FAIL "$o"
cp $NEW/lilith_memory/privacy_governance.py $EV/pg.bak; echo "# tamper" >> $NEW/lilith_memory/privacy_governance.py
o=$(b4 d $FAKESHA); rec B-4-d INFO "$o"
[[ $o == "F9C2_B4 FAIL"* && $o == *coreapi-f9c-privacy_governance.py* ]] && rec B-4-d-tamper PASS "one changed byte in a deployed F9-C file is refused" || rec B-4-d-tamper FAIL ""
cp $EV/pg.bak $NEW/lilith_memory/privacy_governance.py; chown lilith:lilith $NEW/lilith_memory/privacy_governance.py
F8R4_SHA=$(grep '^CHECK f8r4-release-sha ' $EV/b4-c.log | awk '{print $4}')
rec B-4-f8r4-digest INFO "$F8R4_SHA"

echo "#### V1 D-1: U-1 preserve, f9c2 install, ledger carried forward, canary turns with no key"
LED0=$(sha256sum < $LED | cut -c1-64)
F8_SIM=1 F8R4_RELEASE_SHA=$F8R4_SHA bash $P9/bin/preserve_f8r4.sh > $EV/u1.log 2>&1 && grep -q F8R4_PRESERVED $EV/u1.log \
  && rec U-1 PASS "$(tail -1 $EV/u1.log | cut -c1-120)" || { rec U-1 FAIL "$(tail -2 $EV/u1.log | tr '\n' ' ')"; exit 1; }
PRES=$(grep -o 'F8R4_PRESERVED [^ ]*' $EV/u1.log | cut -d' ' -f2); Q=$(sed -n 's/^quarantine=//p' $PRES/record)
QLED=$Q/var-lib/private-hermes-provider-gate-dev/ledger.log
[[ $(sha256sum < $QLED | cut -c1-64) == "$LED0" ]] && rec U-1-ledger PASS "exhausted ledger preserved in the quarantine" || rec U-1-ledger FAIL ""
bash $P9/bin/backup_pre_install.sh >/dev/null
F8_SIM=1 bash $P9/bin/install.sh > $EV/u2.log 2>&1 && grep -q "F8_INSTALL_STAGED f293e72-f9c2" $EV/u2.log && rec U-2 PASS staged || { rec U-2 FAIL "$(tail -2 $EV/u2.log)"; exit 1; }
# U-2b (the G-0 correction): carry the exhausted F8r4 ledger forward BEFORE the f9c2 gate first starts (copy; the
# preserved quarantine stays byte-identical for restore_f8r4). Without it the new gate writes "RESET initial-ledger".
install -d -o root -g root -m 0700 /var/lib/private/hermes-provider-gate-dev
cp -p $QLED $LED
rec U-2b INFO "ledger carried: $(sha256sum < $LED | cut -c1-16) lines=$(wc -l < $LED)"
bash $P9/bin/provision_console_token.sh >/dev/null
R9=/opt/hermes-gateway-dev/current
$R9/venv/bin/python -I -B $R9/bin/verify_release.py --full > $EV/u4-verify.log 2>&1; rec U-4-verify INFO "rc=$? $(tail -1 $EV/u4-verify.log)"
REQ0=$(wc -l < $SY/requests.jsonl); J0=$(gatej | wc -l)
systemctl start hermes-gateway-dev; wait9901 && rec U-4-start PASS "gateway + gate listening" || { rec U-4-start FAIL ""; exit 1; }
hz=$(bash $R9/bin/gate_budget.sh show)
echo "$hz" | grep -q '"key_loaded": false' && echo "$hz" | grep -q '"available": false' && echo "$hz" | grep -q '"budget_used": 5' \
  && rec U-4-gate PASS "no key, budget still exhausted: ${hz:0:170}" || rec U-4-gate FAIL "${hz:0:200}"
[[ $(sha256sum < $LED | cut -c1-64) == "$LED0" ]] && rec U-4-ledger PASS "no initial RESET written; ledger identical to the F8r4 one" || rec U-4-ledger FAIL "$(tail -2 $LED)"
sleep 3; codes=""
for i in 1 2 3; do codes="$codes$(relay "$CAN-$i synthetic drill turn; no personal data." f9c2-g0-d1)/"; done
sleep 2
rec D-1-turns INFO "relay http=[$codes] last=$(python3 -c 'import json;d=json.load(open("'$EV'/relay.json"));print((d.get("state"),(d.get("reply") or "")[:90]))' 2>/dev/null)"
# U-1 moved the F8r4 namespace journal into the quarantine: the live namespace journal is the f9c2 phase only.
fwd=$(gatej | grep -c '"decision": "FORWARDED"'); refused=$(gatej | grep -c '"reason": "KEY_NOT_PROVISIONED"')
probes=$(gatej | grep -c '"reason": "PATH_NOT_ALLOWED"')
[[ $fwd -eq 0 && $refused -eq 3 ]] && rec D-1-gate PASS "gate: FORWARDED=0, KEY_NOT_PROVISIONED=$refused (one per turn), local PATH_NOT_ALLOWED metadata probes=$probes"   || rec D-1-gate FAIL "forwarded=$fwd key_refusals=$refused probes=$probes"
[[ $(wc -l < $SY/requests.jsonl) -eq $REQ0 ]] && rec D-1-no-upstream PASS "0 requests reached the upstream" || rec D-1-no-upstream FAIL "$(( $(wc -l < $SY/requests.jsonl) - REQ0 ))"
[[ $(sha256sum < $LED | cut -c1-64) == "$LED0" ]] && rec D-1-ledger PASS "ledger byte-identical after the turns (nothing reserved or spent)" || rec D-1-ledger FAIL ""
rows=$(python3 - $HH/state.db "$CAN" <<'PY'
import sqlite3, sys
c = sqlite3.connect("file:" + sys.argv[1] + "?mode=ro", uri=True)
r = c.execute("select m.role, count(*) from messages m join sessions s on s.id=m.session_id where m.content like ? group by m.role",
              ("%" + sys.argv[2] + "%",)).fetchall()
src = sorted({x[0] for x in c.execute("select source from sessions")})
print(dict(r), "sessions.source=", src, "sessions=", c.execute("select count(*) from sessions").fetchone()[0])
PY
)
[[ $rows == *"'user': 3"* ]] && rec D-1-state-db PASS "canary rows in Hermes state.db: $rows" || rec D-1-state-db FAIL "$rows"

echo "#### restore: f9c2 R-2 + restore_f8r4 (no FORGET ran here: full inventory identical)"
bash $R9/bin/rollback.sh remove > $EV/r2.log 2>&1 && grep -q F8_ROLLBACK_REMOVED $EV/r2.log && rec R-2 PASS "" || rec R-2 FAIL "$(tail -2 $EV/r2.log | tr '\n' ' ')"
F8_SIM=1 bash $P9/bin/restore_f8r4.sh "$PRES" > $EV/r3.log 2>&1 && grep -q F8R4_RESTORED $EV/r3.log \
  && rec R-3 PASS "$(grep -E '^inventory:|F8R4_RESTORED' $EV/r3.log | paste -sd' ' | cut -c1-200)" || rec R-3 FAIL "$(tail -3 $EV/r3.log | tr '\n' ' ')"
[[ $(sha256sum < $LED | cut -c1-64) == "$LED0" ]] && rec R-3-ledger PASS "restored F8r4 ledger identical (still 5/5)" || rec R-3-ledger FAIL ""
