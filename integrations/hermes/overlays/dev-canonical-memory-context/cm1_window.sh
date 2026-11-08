#!/usr/bin/env bash
# cm1: the canonical-memory read route on DEV (lilith-dev-01 only). Root only. Payload: /root/cm1/payload (root 0700),
# exactly the PAYLOAD files below. Phases (each prints one CM1_<PHASE>_<RESULT> line last):
#   preflight            read-only: every pin, the FORGET state, Privacy READY, the budget, and the no-write baseline
#   install              stop the gateway; install the context service + socket units, the adapter overlay and a v2
#                        owner grant (72 h, ALL lilith_os sessions, forgetScope CANONICAL_RECORDS_ONLY); raise the
#                        provider gate by EXACTLY 2 requests; re-pin; verify; start gate + gateway; root socket probes.
#                        Any failure after the first change runs `revert` automatically.
#   turn <1|2>           one console turn on a NEW session (T1 recall, T2 missing information); reply kept 0600
#   check                read-only: the no-write comparison against the preflight baseline
#   close                lower the gate back to its exact pre-install gate.json (budget exhausted again); the route stays
#   revert               idempotent: everything back to the pre-install bytes, gateway restarted on the e1 adapter
# Never touched: the signer, witness, broker, Core API, Privacy and memory databases, the ledger (only the gate itself
# appends to it), the host tree, any key. Nothing is deleted except files this script created.
set -Eeuo pipefail
umask 022
PHASE=${1:?usage: cm1_window.sh preflight|install|turn N|check|close|revert}
W=/root/cm1
PAY=${W}/payload
BASE=/opt/hermes-gateway-dev
E1ID=f293e72-f9c2-cog1-wm1-g1-r1-w1-m1-p1-e1
HH=/home/lilith/.hermes-dev
PL=${HH}/plugins/lilith_os
GW=hermes-gateway-dev.service
GATE=hermes-provider-gate-dev.service
API=lilith-os-api-dev.service
GJ=/etc/hermes-provider-gate-dev/gate.json
CRIT=/etc/hermes-gateway-dev/critical.sha256
LEDGER=/var/lib/private/hermes-provider-gate-dev/ledger.log
SVC_DIR=/usr/local/lib/lilith-canonical-context
SVC=${SVC_DIR}/canonical_context_service.py
SD=/etc/systemd/system
SOCK_UNIT=lilith-first-memory-context.socket
SVC_UNIT=lilith-first-memory-context@.service
SOCK=/run/lilith-first-memory-context.sock
GRANT=/etc/lilith-first-memory-dev/hermes-owner-channel.json
SIGNER=/opt/lilith-authority-dev/releases/d82f7dac669f37c494beebf9bbb99dffdb6c23f5
HOSTTREE=/opt/lilith-first-memory-dev/current
DRILL=/home/lilith/.hermes/lilith-os-dev/f9-drill
FORGET=/var/lib/hermes-forget
BOOT=cb0d71da
declare -A PAYLOAD=(
  [adapter.cm1.py]=f89303601c2b6901e4d5111242a4949a9ce1df7249a9d358edda6c69b021c0e3
  [adapter.e1.py]=8c3b00552d83adb4e7d6c0af5a9aa081cb60d92879dc14db3baf71537ca32a4a
  [lilith_memory_context.py]=a32c5e4120d26bd2b7e9e72726e5f8349e714c10e51940d1eaa31cac6022dfd6
  [canonical_context_service.py]=70ef79cf7c1ecdd0ece420f65881f8ddae62d91dccd10e072c9e439535b02e2e
  [lilith-first-memory-context.socket]=d1370434aa754516ea1e13db7187b8bbbcc85829de30141d8f34964beead0f86
  [lilith-first-memory-context@.service]=930d4c704fed1540f0ca55b4cf9ac1183e782f5da1297bad2385d046ca888427
)
CLI_SHA=46f2156515b544770a264d538b183ba5f9d7fe869fb220623a565ffb62e56d07
HMC_SHA=a32c5e4120d26bd2b7e9e72726e5f8349e714c10e51940d1eaa31cac6022dfd6
PLUGIN_INIT_SHA=8adb7d5085a96d5edbc72f43e8dfd089ed5c8434f3cedd76b418f930746df37c
STAGE=none
out() { echo "$*"; }
sha() { sha256sum "$1" | cut -d' ' -f1; }
die() { out "CM1_${PHASE^^}_FAIL $*"; exit 1; }
hf() { python3 -I -c 'import json,sys; d=json.loads(sys.argv[1]); print(" ".join(str(d.get(k)) for k in sys.argv[2:]))' "$@" 2>/dev/null; }
budget() { hf "$(curl -s -m 5 http://127.0.0.1:9911/healthz)" key_loaded state budget_used budget_requests available day_requests; }
ledger() { echo "lines=$(wc -l < ${LEDGER}) R=$(grep -c '^R ' ${LEDGER}) sha=$(sha ${LEDGER} | cut -c1-16)"; }
verify() { ${BASE}/current/venv/bin/python -I -B ${BASE}/current/bin/verify_release.py --full 2>&1 | tail -1; }
gwstate() { systemctl show ${GW} -p ActiveState -p MainPID | LC_ALL=C sort | paste -sd' '; }
gw_stopped() { local s; s=$(gwstate); [[ ${s} == "ActiveState=inactive MainPID=0" || ${s} == "ActiveState=failed MainPID=0" ]]; }
gate_up() { local end=$((SECONDS + 90)); while (( SECONDS < end )); do [[ $(curl -s -m 2 -o /dev/null -w '%{http_code}' http://127.0.0.1:9911/healthz) == 200 ]] && return 0; sleep 1; done; return 1; }
console_up() { local end=$((SECONDS + 150)); while (( SECONDS < end )); do [[ $(curl -s -m 2 -o /dev/null -w '%{http_code}' http://127.0.0.1:9901/) == 200 ]] && return 0; sleep 2; done; return 1; }
no_forget_pending() { [[ ! -e ${FORGET}/in-progress && -z $(ls -A ${FORGET}/intent 2>/dev/null) ]]; }
take_forget_lock() { exec 9>>"${FORGET}/state/.lock"; flock -w 30 9 || die "FORGET executor busy"; }

baseline() {   # content-free digests of everything the route must NOT write (as lilith, read-only, like the host)
  runuser -u lilith -- python3 -I - "${DRILL}" "$(systemctl show ${API} -p Environment --value | tr ' ' '\n' | sed -n 's/^LILITH_DB_PATH=//p')" "${HH}" <<'PY'
import glob, hashlib, json, os, sqlite3, sys
drill, core, hh = sys.argv[1:4]
def db(path):
    c = sqlite3.connect("file:%s?mode=ro" % path, uri=True, timeout=5.0)
    out = {}
    for (t,) in c.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"):
        rows = c.execute('SELECT * FROM "%s"' % t).fetchall()
        out[t] = "%d:%s" % (len(rows), hashlib.sha256("\n".join(sorted(repr(tuple(r)) for r in rows)).encode()).hexdigest()[:16])
    c.close()
    return hashlib.sha256(json.dumps(out, sort_keys=True).encode()).hexdigest()[:16], sum(int(v.split(":")[0]) for v in out.values())
res = {}
for name in ("cognitive_memory.f9drill.db", "privacy_governance.f9drill.db"):
    res[name] = db(os.path.join(drill, name))
res["core"] = db(core)
mem = sorted(glob.glob(os.path.join(hh, "memories", "**"), recursive=True))
res["hermes_memories"] = hashlib.sha256("".join(p + (open(p, "rb").read().hex() if os.path.isfile(p) else "") for p in mem).encode()).hexdigest()[:16]
res["request_dumps"] = len(glob.glob(os.path.join(hh, "sessions", "request_dump_*")))
print(json.dumps(res, sort_keys=True))
PY
}
signer_head() {   # content digest of the signer, witness and broker state (files only; nothing opened for write)
  local d; for d in /var/lib/lilith-authority-dev /var/lib/lilith-recovery-witness /var/lib/lilith-memory-broker; do
    printf '%s=%s ' "${d##*/}" "$(find "$d" -type f -print0 2>/dev/null | LC_ALL=C sort -z | xargs -0 -r sha256sum | sha256sum | cut -c1-16)"
  done; echo; }

preconditions() {
  [[ $(id -u) == 0 ]] || die "not root"
  [[ $(hostname) == lilith-dev-01 ]] || die "wrong host"
  [[ $(cut -c1-8 /proc/sys/kernel/random/boot_id) == "${BOOT}" ]] || die "boot changed: Privacy unlock needed first"
  [[ -f /run/lilith-privacy-fresh/verified ]] || die "Privacy freshness marker absent"
  no_forget_pending || die "FORGET pending"
  [[ $(readlink -f ${BASE}/current) == ${BASE}/releases/${E1ID} ]] || die "gateway current is not e1"
  [[ $(readlink -f /opt/lilith-authority-dev/current) == "${SIGNER}" ]] || die "signer release is not d82f7da"
  [[ $(sha ${SIGNER}/lilith_authority_root/cli.py) == "${CLI_SHA}" ]] || die "release cli differs"
  [[ $(sha ${HOSTTREE}/services/owner-memory-control/lilith_owner_memory/hermes_memory_context.py) == "${HMC_SHA}" ]] || die "host tree context module differs"
  [[ $(sha ${PL}/__init__.py) == "${PLUGIN_INIT_SHA}" ]] || die "plugin __init__ differs"
  [[ $(stat -c '%U %a %F' "${PAY}") == "root 700 directory" ]] || die "payload dir must be root 0700"
  [[ $(find "${PAY}" -mindepth 1 | wc -l) -eq ${#PAYLOAD[@]} ]] || die "payload must hold exactly the payload files"
  local f; for f in "${!PAYLOAD[@]}"; do [[ $(sha "${PAY}/$f") == "${PAYLOAD[$f]}" ]] || die "payload digest $f"; done
}

state_line() {
  out "STATE adapter=$(sha ${PL}/adapter.py | cut -c1-16) ctxmod=$( [[ -e ${PL}/lilith_memory_context.py ]] && sha ${PL}/lilith_memory_context.py | cut -c1-16 || echo absent)" \
      "service=$( [[ -e ${SVC} ]] && sha ${SVC} | cut -c1-16 || echo absent) units=$(ls ${SD}/${SOCK_UNIT} ${SD}/${SVC_UNIT} 2>/dev/null | wc -l)" \
      "socket=$(systemctl show ${SOCK_UNIT} -p ActiveState --value 2>/dev/null) grant=$( [[ -e ${GRANT} ]] && echo present || echo absent)" \
      "gate_json=$(sha ${GJ} | cut -c1-16) critical=$(sha ${CRIT} | cut -c1-16) gw=\"$(gwstate)\""
}

probe() {   # one root request on the context socket: content-free summary (kinds, value digests, flags)
  python3 -I - "$1" "$2" <<'PY'
import hashlib, json, socket, sys
channel, session = sys.argv[1], sys.argv[2]
s = socket.socket(socket.AF_UNIX); s.settimeout(60); s.connect("/run/lilith-first-memory-context.sock")
s.sendall(json.dumps({"v": 1, "channel": channel, "sessionId": session}).encode()); s.shutdown(socket.SHUT_WR)
data = b""
while True:
    chunk = s.recv(4096)
    if not chunk: break
    data += chunk
d = json.loads(data)
print("PROBE", channel, d.get("status"), d.get("reason"), "ownerChannel=%s" % d.get("ownerChannel"),
      "forgetScope=%s" % d.get("forgetScope"),
      [(m["kind"], m["sensitivity"], len(m["value"]), hashlib.sha256(m["value"].encode()).hexdigest()[:12]) for m in d.get("memories", [])])
PY
}

revert() {   # idempotent
  STAGE=reverting
  out "--- revert"
  systemctl stop ${GW} || true
  for _ in $(seq 30); do gw_stopped && break; sleep 1; done
  gw_stopped || die "gateway did not stop for revert"
  systemctl stop ${SOCK_UNIT} 2>/dev/null || true
  install -o root -g root -m 0644 ${PAY}/adapter.e1.py ${PL}/adapter.py.cm1-new && mv -f ${PL}/adapter.py.cm1-new ${PL}/adapter.py
  rm -f ${PL}/lilith_memory_context.py ${GRANT} ${SD}/${SOCK_UNIT} ${SD}/${SVC_UNIT} ${SVC}
  [[ -d ${SVC_DIR} ]] && rmdir ${SVC_DIR} || true
  if [[ -f ${W}/gate.json.pre ]] && [[ $(sha ${GJ}) != $(sha ${W}/gate.json.pre) ]]; then
    cp -p ${W}/gate.json.pre ${GJ}; systemctl restart ${GATE}; gate_up || die "gate not up after revert"
  fi
  bash ${BASE}/current/bin/pin_critical.sh ${BASE}/current >/dev/null
  [[ -f ${W}/critical.sha256.pre ]] && { [[ $(sha ${CRIT}) == $(sha ${W}/critical.sha256.pre) ]] || die "critical set differs from pre-install after revert"; }
  [[ $(verify) == "F8_VERIFY_PASS full ${E1ID}" ]] || die "e1 verify after revert"
  systemctl start ${GW}; console_up || die "console not up after revert"
  state_line; out "BUDGET $(budget)"
  STAGE=done
  out "CM1_REVERT_PASS"
}

on_exit() {
  local rc=$?
  [[ ${rc} -ne 0 && ${STAGE} == changing ]] || return 0
  out "CM1_INSTALL_FAIL after changes: reverting"
  ( trap - EXIT; revert ) || out "CM1_REVERT_FAIL re-run: cm1_window.sh revert"
}
trap on_exit EXIT

case ${PHASE} in
  preflight)
    preconditions
    [[ $(sha ${PL}/adapter.py) == "${PAYLOAD[adapter.e1.py]}" ]] || die "installed adapter is not e1's"
    [[ ! -e ${PL}/lilith_memory_context.py && ! -e ${SVC} && ! -e ${GRANT} && ! -e ${SD}/${SOCK_UNIT} && ! -e ${SD}/${SVC_UNIT} ]] || die "cm1 already (partly) installed"
    [[ $(verify) == "F8_VERIFY_PASS full ${E1ID}" ]] || die "e1 does not verify"
    [[ $(systemctl show ${GW} -p ActiveState --value) == active && $(systemctl show ${GATE} -p ActiveState --value) == active ]] || die "gateway or gate not active"
    state_line; out "BUDGET $(budget)"; out "LEDGER $(ledger)"; out "SIGNER $(signer_head)"; out "BASELINE $(baseline)"
    out "CANONICAL_CONFIG $(sha /etc/lilith-first-memory-dev/canonical-config.json | cut -c1-16)"
    out "CM1_PREFLIGHT_PASS"
    ;;
  install)
    preconditions
    [[ ! -e ${W}/install.started ]] || die "install already ran once (use revert, then a new go)"
    [[ $(sha ${PL}/adapter.py) == "${PAYLOAD[adapter.e1.py]}" ]] || die "installed adapter is not e1's"
    [[ ! -e ${SVC} && ! -e ${GRANT} && ! -e ${SD}/${SOCK_UNIT} ]] || die "cm1 already (partly) installed"
    [[ $(verify) == "F8_VERIFY_PASS full ${E1ID}" ]] || die "e1 does not verify before"
    read -r KEY ST USED LIMIT AVAIL DAY < <(budget)
    [[ ${KEY} == True && ${LIMIT} == 5 && ${USED} =~ ^[0-9]+$ && ${USED} -ge 5 ]] || die "budget is not exhausted at 5 (${KEY} ${ST} ${USED} ${LIMIT})"
    NEWLIMIT=$((USED + 2))
    (( NEWLIMIT <= 50 )) || die "verifier caps budget_requests at 50"
    [[ $(grep -c '"budget_requests": 5,' ${GJ}) == 1 ]] || die "gate.json has no single budget_requests 5 line"
    touch ${W}/install.started
    baseline > ${W}/baseline.pre; signer_head > ${W}/signer.pre; ledger > ${W}/ledger.pre
    cp -p ${GJ} ${W}/gate.json.pre; cp -p ${CRIT} ${W}/critical.sha256.pre
    out "PRE budget=${USED}/${LIMIT} -> ${NEWLIMIT} (exactly 2 requests) $(cat ${W}/ledger.pre)"
    systemctl stop ${GW} || true
    for _ in $(seq 40); do gw_stopped && break; sleep 1; done
    gw_stopped || die "gateway did not stop"
    take_forget_lock
    no_forget_pending || die "FORGET pending"
    STAGE=changing
    install -d -o root -g root -m 0755 ${SVC_DIR}
    install -o root -g root -m 0644 ${PAY}/canonical_context_service.py ${SVC}
    install -o root -g root -m 0644 "${PAY}/${SOCK_UNIT}" ${SD}/${SOCK_UNIT}
    install -o root -g root -m 0644 "${PAY}/${SVC_UNIT}" "${SD}/${SVC_UNIT}"
    install -o root -g root -m 0644 ${PAY}/lilith_memory_context.py ${PL}/lilith_memory_context.py
    install -o root -g root -m 0644 ${PAY}/adapter.cm1.py ${PL}/adapter.py.cm1-new && mv -f ${PL}/adapter.py.cm1-new ${PL}/adapter.py
    python3 -I - ${GRANT} <<'PY'
import json, os, sys
from datetime import datetime, timedelta, timezone
now = datetime.now(timezone.utc).replace(microsecond=0)
g = {"schemaVersion": 2, "channel": "lilith_os", "sessionScope": "ALL_LILITH_OS_SESSIONS",
     "forgetScope": "CANONICAL_RECORDS_ONLY", "grantedAt": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
     "expiresAt": (now + timedelta(hours=72)).strftime("%Y-%m-%dT%H:%M:%SZ")}
fd = os.open(sys.argv[1], os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
with os.fdopen(fd, "w", encoding="ascii") as f:
    f.write(json.dumps(g, sort_keys=True) + "\n")
print("GRANT", g["grantedAt"], "->", g["expiresAt"])
PY
    python3 -I - ${GJ} ${NEWLIMIT} <<'PY'
import json, os, sys
path, new_limit = sys.argv[1], int(sys.argv[2])
old = open(path, "rb").read()
new = old.replace(b'"budget_requests": 5,', b'"budget_requests": %d,' % new_limit, 1)
a, b = json.loads(old), json.loads(new)
assert a["budget_requests"] == 5 and b["budget_requests"] == new_limit
assert {k: v for k, v in a.items() if k != "budget_requests"} == {k: v for k, v in b.items() if k != "budget_requests"}
st = os.stat(path); tmp = path + ".cm1-new"
open(tmp, "wb").write(new); os.chown(tmp, st.st_uid, st.st_gid); os.chmod(tmp, st.st_mode & 0o7777); os.replace(tmp, path)
print("GATE budget_requests 5 ->", new_limit)
PY
    bash ${BASE}/current/bin/pin_critical.sh ${BASE}/current
    V=$(verify); out "VERIFY ${V}"; [[ ${V} == "F8_VERIFY_PASS full ${E1ID}" ]] || die "verify after install"
    systemctl start ${SOCK_UNIT}; [[ $(systemctl show ${SOCK_UNIT} -p ActiveState --value) == active ]] || die "socket not active"
    [[ $(stat -c '%U:%G %a' ${SOCK}) == "root:lilith 660" ]] || die "socket owner/mode"
    systemctl restart ${GATE}; gate_up || die "gate not up"
    read -r KEY ST USED2 LIMIT2 AVAIL2 DAY2 < <(budget)
    [[ ${USED2} == "${USED}" && ${LIMIT2} == "${NEWLIMIT}" && ${AVAIL2} == True ]] || die "gate budget not ${USED}/${NEWLIMIT}"
    out "PROBE_BEGIN"; probe lilith_os cm1-probe-owner; probe telegram cm1-probe-telegram; out "PROBE_END"
    systemctl start ${GW}; console_up || die "console not up"
    [[ $(ledger) == "$(cat ${W}/ledger.pre)" ]] || die "ledger moved during install"
    exec 9>&-
    STAGE=done
    state_line; out "BUDGET $(budget)"
    out "CM1_INSTALL_PASS"
    ;;
  turn)
    N=${2:?turn number}
    case ${N} in 1) MSG="Do you remember how we first began, you and me?";; 2) MSG="What is my favourite food?";; *) die "turn 1 or 2";; esac
    [[ -e ${W}/install.started && ! -e ${W}/turn${N}.reply ]] || die "not installed, or turn ${N} already ran"
    no_forget_pending || die "FORGET pending"
    read -r KEY ST USED LIMIT AVAIL DAY < <(budget)
    [[ ${AVAIL} == True ]] || die "no budget left (${USED}/${LIMIT})"
    SESSION="cm1-t${N}-$(head -c6 /dev/urandom | od -An -tx1 | tr -d ' \n')"
    L0=$(grep -c '^R ' ${LEDGER}); T0=$(date -u +%FT%TZ)
    out "TURN ${N} session=${SESSION} budget_before=${USED}/${LIMIT} message=\"${MSG}\""
    python3 -I - "${MSG}" "${SESSION}" "${W}/turn${N}.reply" <<'PY'
import json, os, sys, time, urllib.error, urllib.request
msg, session, keep = sys.argv[1:4]
tok = next(l.split("=", 1)[1].strip() for l in open("/home/lilith/.hermes-dev/.env") if l.startswith("LILITH_OS_TOKEN="))
req = urllib.request.Request("http://127.0.0.1:9901/", data=json.dumps({"message": msg, "session": session}).encode(),
                             headers={"Content-Type": "application/json", "X-LILITH-OS-Token": tok}, method="POST")
t = time.time()
try:
    with urllib.request.urlopen(req, timeout=200) as r:
        body, status = json.loads(r.read() or b"{}"), r.status
except urllib.error.HTTPError as e:
    body, status = {}, e.code
except Exception as e:
    body, status = {}, "EXC_" + type(e).__name__
fd = os.open(keep, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
with os.fdopen(fd, "w", encoding="utf-8") as f:
    f.write(body.get("reply") or "")
print("TURN_RESULT", status, body.get("state"), "chars=%d" % len(body.get("reply") or ""), "secs=%.1f" % (time.time() - t))
PY
    L1=$(grep -c '^R ' ${LEDGER}); out "PROVIDER_REQUESTS_THIS_TURN $((L1 - L0)) budget_after=$(budget)"
    out "GATE_DECISIONS $(journalctl --namespace=hermes-gateway-dev -u ${GATE} --since "${T0}" --no-pager -o cat 2>/dev/null | grep -oE '"decision": "[A-Z_]+"' | sort | uniq -c | tr -s ' ' | paste -sd,)"
    out "CONTEXT_RUNS $(journalctl -t lilith-first-memory-context --since "${T0}" --no-pager -o cat 2>/dev/null | wc -l) log_lines; units_started $(journalctl --since "${T0}" --no-pager -o cat 2>/dev/null | grep -c 'lilith-first-memory-context@')"
    out "REPLY_BEGIN"; cat ${W}/turn${N}.reply; echo; out "REPLY_END"
    out "CM1_TURN${N}_DONE"
    ;;
  check)
    [[ -e ${W}/baseline.pre ]] || die "no baseline"
    POST=$(baseline); out "BASELINE_PRE  $(cat ${W}/baseline.pre)"; out "BASELINE_POST ${POST}"
    python3 -I - "$(cat ${W}/baseline.pre)" "${POST}" <<'PY'
import json, sys
a, b = json.loads(sys.argv[1]), json.loads(sys.argv[2])
for k in sorted(a):
    print("CMP", k, "EQUAL" if a[k] == b[k] else "DIFF %s -> %s" % (a[k], b[k]))
PY
    out "SIGNER_PRE $(cat ${W}/signer.pre) SIGNER_POST $(signer_head)"
    S=$(runuser -u lilith -- python3 -I - "${HH}" <<'PY'
import glob, os, sqlite3, sys
hh = sys.argv[1]
NOTE = "[LILITH canonical memory:"
try:
    c = sqlite3.connect("file:%s?mode=ro" % os.path.join(hh, "state.db"), uri=True, timeout=5.0)
    hits = 0
    for (t,) in c.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall():
        cols = [r[1] for r in c.execute('PRAGMA table_info("%s")' % t)]
        for col in cols:
            try:
                hits += c.execute('SELECT COUNT(*) FROM "%s" WHERE CAST("%s" AS TEXT) LIKE ?' % (t, col), ("%" + NOTE + "%",)).fetchone()[0]
            except sqlite3.Error:
                pass
    print("STATE_DB note_header_anywhere=%d" % hits)
except sqlite3.Error as e:
    print("STATE_DB UNREADABLE", type(e).__name__)
dumps = glob.glob(os.path.join(hh, "sessions", "request_dump_*"))
print("REQUEST_DUMPS %d with_note=%d" % (len(dumps), sum(1 for p in dumps if NOTE.encode() in open(p, "rb").read())))
other = [p for p in glob.glob(os.path.join(hh, "**"), recursive=True) if os.path.isfile(p) and os.path.getsize(p) < 50_000_000
         and not p.endswith(("state.db", "state.db-wal", "state.db-shm"))
         and not os.path.relpath(p, hh).startswith(("plugins/", "lilith_router/")) and NOTE.encode() in open(p, "rb").read()]
print("HERMES_HOME_FILES_WITH_NOTE %d %s" % (len(other), [os.path.relpath(p, hh) for p in other][:5]))
PY
); out "${S}"
    out "JOURNAL_NOTE_HITS $(journalctl --namespace=hermes-gateway-dev --since "$(stat -c %y ${W}/install.started | cut -d. -f1)" --no-pager -o cat 2>/dev/null | grep -c 'LILITH canonical memory:')"
    out "CANONICAL_CONFIG $(sha /etc/lilith-first-memory-dev/canonical-config.json | cut -c1-16) FORGET_PENDING $(no_forget_pending && echo no || echo YES)"
    state_line
    out "CM1_CHECK_DONE"
    ;;
  close)
    [[ -f ${W}/gate.json.pre ]] || die "no pre-install gate.json"
    [[ ! -e ${W}/closed ]] || die "already closed"
    systemctl stop ${GW}; for _ in $(seq 40); do gw_stopped && break; sleep 1; done; gw_stopped || die "gateway did not stop"
    take_forget_lock
    cp -p ${W}/gate.json.pre ${GJ}
    bash ${BASE}/current/bin/pin_critical.sh ${BASE}/current
    V=$(verify); [[ ${V} == "F8_VERIFY_PASS full ${E1ID}" ]] || die "verify after close"
    systemctl restart ${GATE}; gate_up || die "gate not up"
    systemctl start ${GW}; console_up || die "console not up"
    exec 9>&-
    touch ${W}/closed
    state_line; out "BUDGET $(budget)"; out "LEDGER $(ledger)"
    out "CM1_CLOSE_PASS"
    ;;
  revert)
    [[ $(id -u) == 0 && $(hostname) == lilith-dev-01 ]] || die "root on lilith-dev-01 only"
    take_forget_lock
    revert
    ;;
  *) die "unknown phase" ;;
esac
