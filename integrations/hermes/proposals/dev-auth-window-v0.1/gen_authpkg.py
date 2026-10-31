# Generates the DEV auth window scripts. Local only. python -I -B gen_authpkg.py <package> <e1 package> <app.py sha256>
import re, shutil, sys
from pathlib import Path
pkg, e1, APP = Path(sys.argv[1]), Path(sys.argv[2]), sys.argv[3]
assert re.fullmatch(r"[0-9a-f]{64}", APP)
S = pkg / "scripts"; S.mkdir(parents=True, exist_ok=True)
DBPY = re.search(r"DBPY=\$\(cat <<'PY'\n(.*?)\nPY\n\)\n", (e1 / "scripts/s6_shadow_test.sh").read_text(encoding="ascii"), re.S).group(1)
SEND = re.search(r"(send\(\) \{.*?\n\}\n)dlog\(\)", (e1 / "scripts/s6_shadow_test.sh").read_text(encoding="ascii"), re.S).group(1)
DLOG = re.search(r"(dlog\(\) \{.*?\nPY\n\}\n)", (e1 / "scripts/s6_shadow_test.sh").read_text(encoding="ascii"), re.S).group(1)
PREV_NOTE = "PREPARED, NOT APPROVED, NOT RUN"
COMMON = r"""set -u
# %(title)s (""" + PREV_NOTE + r"""). DEV auth window. Tokens are never printed or passed on a command line.
HH=/home/lilith/.hermes-dev
BASE=/opt/hermes-gateway-dev
APPROOT=/home/lilith/.hermes/lilith-os-dev
API=lilith-os-api-dev.service
GW=hermes-gateway-dev.service
GATE=hermes-provider-gate-dev.service
NS=hermes-gateway-dev
D=/etc/systemd/system/lilith-os-api-dev.service.d
F=${D}/auth.conf
ENVF=/etc/lilith-os-api-dev/auth.env
W=/root/auth-window-20261101
NIC=10.20.0.3
LOCAL=http://127.0.0.1:8765
REMOTE=http://${NIC}:8765
REF=88b76a7910fdcb27dc3b7c02e9f18c2c92b8154d10afc9f15f4bc9da90a84e79
RID=f293e72-f9c2-cog1-wm1-g1-r1-w1-m1-p1-e1
APP_SHA=""" + APP + r"""
GW0=407521
LG0="lines=29 sha=5764da8e26246d16"
FAILS=
fail() { echo "CHECK_FAIL $1"; FAILS="${FAILS} $1"; }
want() { [ "$2" = "$3" ] && echo "OK $1 $2" || fail "$1(got_$2_want_$3)"; }
pid() { systemctl show "$1" -p MainPID --value; }
hf() { python3 -I -c 'import json,sys; d=json.loads(sys.argv[1]); print(" ".join(str(d.get(k)) for k in sys.argv[2:]))' "$@" 2>/dev/null; }
budget() { hf "$(curl -s -m 5 http://127.0.0.1:9911/healthz)" key_loaded state budget_used budget_requests available; }
ledger() { echo "lines=$(sudo -n wc -l /var/lib/private/hermes-provider-gate-dev/ledger.log | cut -d' ' -f1) sha=$(sudo -n sha256sum /var/lib/private/hermes-provider-gate-dev/ledger.log | cut -c1-16)"; }
dumps() { sudo -n find ${HH}/sessions -maxdepth 1 -name 'request_dump_*' | wc -l; }
code() { curl -s -o /dev/null -m 10 -w '%%{http_code}' "$@"; }
authed() {   # authed WRITE|READ url [curl args]: the header goes in on stdin
  local name=LILITH_OS_$1_TOKEN hdr=X-LILITH-OS-Read url=$2; shift 2
  [ "${name}" = LILITH_OS_WRITE_TOKEN ] && hdr=X-LILITH-OS-Write
  printf 'header = "%%s: %%s"\n' "${hdr}" "$(sudo -n sed -n "s/^${name}=//p" ${ENVF})" | curl -s -o /dev/null -m 10 -w '%%{http_code}' -K - "$@" "${url}"
}
DB=$(systemctl show ${API} -p Environment --value | tr ' ' '\n' | sed -n 's/^"\{0,1\}LILITH_DB_PATH=\(.*\)$/\1/p' | tr -d '"')
DBPY=$(cat <<'PY'
""" + DBPY + r"""
PY
)
dbcheck() { printf '%%s\n' "${DBPY}" | sudo -n python3 -I -B - "${DB}" "${REF}" 2>&1; }
dbok() { dbcheck | grep -qx LIVE_DB_OK && echo OK_DB || fail db; }
forget() { [ "$(sudo -n find /var/lib/hermes-forget/intent -mindepth 1 -maxdepth 1 | wc -l)" -eq 0 ] && ! sudo -n test -e /var/lib/hermes-forget/in-progress && echo OK_FORGET || fail forget; }
conf() {   # conf WRITE READ focus trust envfile: the whole drop-in, written atomically
  { echo "[Service]"; echo "Environment=\"LILITH_OS_WRITE_AUTH=$1\""; echo "Environment=\"LILITH_OS_READ_AUTH=$2\""
    [ "$3" = 1 ] && echo "Environment=\"LILITH_OS_FOCUS_READ_ONLY=1\""
    [ "$4" = 1 ] && echo "Environment=\"LILITH_OS_TRUST_LOOPBACK=1\""
    [ "$5" = 1 ] && echo "EnvironmentFile=${ENVF}"; } | sudo -n tee ${F}.new >/dev/null
  sudo -n chmod 0644 ${F}.new; sudo -n mv -f ${F}.new ${F}; sudo -n systemctl daemon-reload
}
health() { for _ in $(seq 1 30); do [ "$(code ${LOCAL}/health)" = 200 ] && return 0; sleep 1; done; return 1; }
restart() { sudo -n systemctl restart ${API}; health || fail api_not_healthy; }
current() { sudo -n readlink -f ${APPROOT}/current; }
link() { sudo -n ln -sfn "$1" ${APPROOT}/.current.auth; sudo -n chown -h lilith:lilith ${APPROOT}/.current.auth; sudo -n mv -Tf ${APPROOT}/.current.auth ${APPROOT}/current; }
appsha() { sudo -n sha256sum "$(current)/app.py" | cut -c1-64; }
finish() { echo "T1 $(date -u +%%FT%%TZ)"; if [ -z "${FAILS}" ]; then [ -n "${2:-}" ] && sudo -n touch ${W}/$2; echo "$1 PASS"; else echo "$1 FAIL:${FAILS}"; exit 1; fi; }
echo "HOST $(hostname) T0 $(date -u +%%FT%%TZ)"
[ "$(hostname)" = lilith-dev-01 ] || { echo "WRONG_HOST"; exit 3; }
"""
SCRIPTS = {}
SCRIPTS["a0_preflight_ro.sh"] = ("A0 read-only preflight", r"""
want current "$(sudo -n readlink -f ${BASE}/current)" "${BASE}/releases/${RID}"
want gateway "$(pid ${GW})" ${GW0}
want gate_active "$(systemctl show ${GATE} -p ActiveState --value)" active
want budget "$(budget)" "True OK 3 5 True"
want ledger "$(ledger)" "${LG0}"
want dumps "$(dumps)" 28
dbok; forget
want no_failed_units "$(systemctl list-units --failed --no-legend | wc -l)" 0
sudo -n test ! -e ${F} && echo OK_no_dropin || fail dropin_exists
sudo -n test ! -e ${ENVF} && echo OK_no_tokens || fail token_file_exists
sudo -n test ! -e ${W} && echo OK_no_window || fail window_exists
echo "API_PID $(pid ${API}) DROPINS [$(systemctl show ${API} -p DropInPaths --value)] CORE_RELEASE $(current)"
want api_active "$(systemctl show ${API} -p ActiveState --value)" active
want local_health "$(code ${LOCAL}/health)" 200
want nic_health "$(code ${REMOTE}/health)" 200
want nic_address_is_local "$(ip -4 -o addr show | grep -c " ${NIC}/")" 1
want bind_all "$(ss -Hltn 'sport = :8765' | grep -c '0.0.0.0:8765')" 1
want no_local_proxy "$(sudo -n ss -Hltnp | grep -cE 'nginx|caddy|haproxy|envoy|cloudflared|ngrok')" 0
finish A0_PREFLIGHT
""")
SCRIPTS["a1_dropin_open.sh"] = ("A1 write the open drop-in, no restart", r"""
sudo -n test ! -e ${W} || { echo "A1_ABORTED window exists"; exit 3; }
P0=$(pid ${API})
sudo -n install -d -o root -g root -m 0700 ${W}
current | sudo -n tee ${W}/prev >/dev/null
appsha | sudo -n tee ${W}/prevsha >/dev/null
sudo -n install -d -o root -g root -m 0755 ${D}
conf open-acknowledged open-acknowledged 0 0 0
want env_write "$(systemctl show ${API} -p Environment --value | tr ' ' '\n' | grep -c 'LILITH_OS_WRITE_AUTH=open-acknowledged')" 1
want env_read "$(systemctl show ${API} -p Environment --value | tr ' ' '\n' | grep -c 'LILITH_OS_READ_AUTH=open-acknowledged')" 1
want no_restart "$(pid ${API})" "${P0}"
want local_health "$(code ${LOCAL}/health)" 200
finish A1_DROPIN a1.pass
""")
SCRIPTS["ra_remove_dropin.sh"] = ("RA recovery before the merge: remove the drop-in, no restart", r"""
sudo -n rm -f ${F} ${F}.new
sudo -n systemctl daemon-reload
want dropin_gone "$(sudo -n test -e ${F} && echo PRESENT || echo ABSENT)" ABSENT
want local_health "$(code ${LOCAL}/health)" 200
finish RA_REMOVE
""")
SCRIPTS["b0_verify_deploy_ro.sh"] = ("B0 read-only: the merged code is what runs", r"""
sudo -n test -f ${W}/a1.pass || { echo "B0_ABORTED A1 did not pass"; exit 3; }
want app_sha "$(appsha)" "${APP_SHA}"
[ "$(current)" != "$(sudo -n cat ${W}/prev)" ] && echo OK_new_release || fail release_not_new
sudo -n test -f "$(sudo -n cat ${W}/prev)/app.py" && echo OK_prev_kept || fail prev_missing
want gateway "$(pid ${GW})" ${GW0}
want budget "$(budget)" "True OK 3 5 True"
want ledger "$(ledger)" "${LG0}"
dbok; forget
want local_read "$(code ${LOCAL}/os/goals?limit=1)" 200
want remote_read_open "$(code ${REMOTE}/os/goals?limit=1)" 200
current | sudo -n tee ${W}/new >/dev/null
finish B0_VERIFY b0.pass
""")
SCRIPTS["b1_tokens.sh"] = ("B1 create tokens, trust loopback, still open", r"""
sudo -n test -f ${W}/b0.pass || { echo "B1_ABORTED B0 did not pass"; exit 3; }
sudo -n test ! -e ${ENVF} || { echo "B1_ABORTED tokens exist"; exit 3; }
sudo -n install -d -o root -g root -m 0700 /etc/lilith-os-api-dev
sudo -n python3 -I -c 'import os, secrets; f=os.open("'${ENVF}'", os.O_WRONLY|os.O_CREAT|os.O_EXCL, 0o600); os.write(f, ("LILITH_OS_READ_TOKEN=%s\nLILITH_OS_WRITE_TOKEN=%s\n" % (secrets.token_hex(32), secrets.token_hex(32))).encode()); os.close(f)'
want token_mode "$(sudo -n stat -c '%U %a' ${ENVF})" "root 600"
want token_lines "$(sudo -n bash -c "wc -l < ${ENVF}")" 2
conf open-acknowledged open-acknowledged 0 1 1
restart
want local_read "$(code ${LOCAL}/os/goals?limit=1)" 200
dbok
finish B1_TOKENS b1.pass
""")
SCRIPTS["c0_resume_preflight_ro.sh"] = ("C0 read-only: DEV is exactly as the recovery left it", r"""
PREV=$(sudo -n cat ${W}/prev); NEW=$(sudo -n cat ${W}/new)
want on_previous "$(current)" "${PREV}"
want previous_app "$(appsha)" "$(sudo -n cat ${W}/prevsha)"
want new_kept "$(sudo -n sha256sum "${NEW}/app.py" | cut -c1-64)" "${APP_SHA}"
want current "$(sudo -n readlink -f ${BASE}/current)" "${BASE}/releases/${RID}"
want gateway "$(pid ${GW})" ${GW0}
want gate_active "$(systemctl show ${GATE} -p ActiveState --value)" active
want budget "$(budget)" "True OK 3 5 True"
want ledger "$(ledger)" "${LG0}"
want dumps "$(dumps)" 28
dbok; forget
want no_failed_units "$(systemctl list-units --failed --no-legend | wc -l)" 0
want dropin_open "$(sudo -n grep -c 'open-acknowledged' ${F})" 2
want dropin_nothing_else "$(sudo -n grep -cE 'enforced|EnvironmentFile|TRUST_LOOPBACK|FOCUS' ${F})" 0
want tokens_mode "$(sudo -n stat -c '%U %a' ${ENVF})" "root 600"
want tokens_lines "$(sudo -n bash -c "wc -l < ${ENVF}")" 2
want markers "$(sudo -n ls ${W} | LC_ALL=C sort | paste -sd' ')" "a1.pass b0.pass new prev prevsha"
want local_read "$(code ${LOCAL}/os/goals?limit=1)" 200
want nic_read "$(code ${REMOTE}/os/goals?limit=1)" 200
want no_local_proxy "$(sudo -n ss -Hltnp | grep -cE 'nginx|caddy|haproxy|envoy|cloudflared|ngrok')" 0
finish C0_RESUME
""")
SCRIPTS["b1b_resume_new.sh"] = ("B1B back to the merged code with the existing tokens, still open", r"""
sudo -n test -f ${W}/b0.pass || { echo "B1B_ABORTED B0 did not pass"; exit 3; }
sudo -n test ! -e ${W}/b1.pass || { echo "B1B_ABORTED already ran"; exit 3; }
link "$(sudo -n cat ${W}/new)"
conf open-acknowledged open-acknowledged 0 1 1
restart
want app_sha "$(appsha)" "${APP_SHA}"
want local_read "$(code ${LOCAL}/os/goals?limit=1)" 200
dbok
finish B1B_RESUME b1.pass
""")
SCRIPTS["b2_enforce_write.sh"] = ("B2 enforce writes", r"""
sudo -n test -f ${W}/b1.pass || { echo "B2_ABORTED B1 did not pass"; exit 3; }
conf enforced open-acknowledged 0 1 1
restart
want stranger_write "$(code -X POST -H 'content-type: application/json' -d '{}' ${REMOTE}/os/goals)" 401
want write_task "$(code -X POST -H 'content-type: application/json' -d '{}' ${REMOTE}/os/tasks)" 401
want write_draft "$(code -X POST -H 'content-type: application/json' -d '{}' ${REMOTE}/os/drafts)" 401
C=$(authed WRITE ${REMOTE}/os/goals -X POST -H 'content-type: application/json' -d '{}')
[ "${C}" = 400 ] || [ "${C}" = 422 ] && echo "OK owner_write_reaches_validation ${C}" || fail "owner_write(${C})"
C=$(code -X POST -H 'content-type: application/json' -d '{}' ${LOCAL}/os/goals)
[ "${C}" = 400 ] || [ "${C}" = 422 ] && echo "OK router_write_reaches_validation ${C}" || fail "router_write(${C})"
dbok
finish B2_WRITE b2.pass
""")
SCRIPTS["b3_enforce_read.sh"] = ("B3 enforce reads, focus read-only", r"""
sudo -n test -f ${W}/b2.pass || { echo "B3_ABORTED B2 did not pass"; exit 3; }
conf enforced enforced 1 1 1
restart
for p in '/os/goals?limit=1' /os/goals/focus '/os/tasks?limit=1' '/os/drafts?limit=1' /os/world /memory/overview /career/pipeline /audit/recent /system/status /docs /openapi.json; do
  want "stranger ${p}" "$(code ${REMOTE}${p})" 401
done
want wrong_token "$(code -H 'X-LILITH-OS-Read: wrong' ${REMOTE}/os/goals?limit=1)" 401
want stranger_conversation "$(code -X POST -H 'content-type: application/json' -d '{"message":"x"}' ${REMOTE}/os/conversation)" 401
want local_conversation_needs_credential "$(code -X POST -H 'content-type: application/json' -d '{"message":"x"}' ${LOCAL}/os/conversation)" 401
want owner_read "$(authed READ ${REMOTE}/os/goals?limit=1)" 200
want router_read "$(code ${LOCAL}/os/goals?limit=1)" 200
want router_focus "$(code ${LOCAL}/os/goals/focus)" 200
want health_open "$(code ${REMOTE}/health)" 200
dbok
finish B3_READ b3.pass
""")
SCRIPTS["b4_router_turns.sh"] = ("B4 two TEST_ONLY turns with the gate stopped: the router still reads under enforcement", SEND + DLOG + r"""
sudo -n test -f ${W}/b3.pass || { echo "B4_ABORTED B3 did not pass"; exit 3; }
sudo -n test ! -e ${W}/b4.started || { echo "B4_ABORTED already ran"; exit 3; }
DL0=$(sudo -n bash -c "wc -l < ${HH}/logs/lilith-router-decisions.log")
sleep 2; T0=$(date -u '+%Y-%m-%d %H:%M:%S')
sudo -n touch ${W}/b4.started
sudo -n systemctl stop ${GATE}
for _ in $(seq 1 30); do [ "$(ss -Hltn 'sport = :9911' | wc -l)" -eq 0 ] && break; sleep 1; done
if [ "$(ss -Hltn 'sport = :9911' | wc -l)" -ne 0 ]; then fail gate_still_listening; else
  SES=auth-shadow-20261101
  echo "T1 $(send "TEST_ONLY what are my options for application 14?" ${SES}-t1)"; sleep 2
  echo "T2 $(send "TEST_ONLY hey how are you" ${SES}-t2)"; sleep 3
fi
sudo -n systemctl start ${GATE}
for _ in $(seq 1 30); do [ "$(curl -s -m 2 -o /dev/null -w '%{http_code}' http://127.0.0.1:9911/healthz)" = 200 ] && break; sleep 1; done
want budget "$(budget)" "True OK 3 5 True"
want ledger "$(ledger)" "${LG0}"
if [ -z "${FAILS}" ]; then
  want records_t1 "$(dlog ${SES}-t1)" "motivation:shadow/SATISFIED/COHERENCE,GOAL_COMPLETION,workspace:shadow/NO_CANDIDATE/0,reasoning:OPTION_GENERATION/None/shadow,cognitive:shadow,routing:live=False text=0"
  want records_t2 "$(dlog ${SES}-t2)" "routing:live=False text=0"
fi
AL=$(sudo -n journalctl -u ${API} --since "${T0}" -o cat --no-pager | grep -oE '"(GET|POST|PUT|PATCH|DELETE|HEAD) /[^ ]* HTTP/[0-9.]+" [0-9]{3}' | sed -E 's/^"//; s/ HTTP\/[0-9.]+"//' | LC_ALL=C sort | paste -sd,)
want router_reads "${AL}" 'GET /os/drafts?limit=200 200,GET /os/goals/focus 200,GET /os/goals?limit=200 200,GET /os/tasks?limit=200 200,GET /os/world?entity_type=career.application&entity_id=14 200'
want gateway "$(pid ${GW})" ${GW0}
want forwarded "$(sudo -n journalctl --namespace=${NS} -u ${GATE} --since "${T0}" --no-pager -o cat | grep -c '"decision": "FORWARDED"')" 0
dbok
finish B4_TURNS b4.pass
""")
SCRIPTS["b5_rollback_proof.sh"] = ("B5 return to the previous Core API and forward again, once", r"""
sudo -n test -f ${W}/b4.pass || { echo "B5_ABORTED B4 did not pass"; exit 3; }
sudo -n test ! -e ${W}/b5.started || { echo "B5_ABORTED already ran"; exit 3; }
sudo -n touch ${W}/b5.started
PREV=$(sudo -n cat ${W}/prev); NEW=$(sudo -n cat ${W}/new)
T_A=$(date +%s)
conf open-acknowledged open-acknowledged 0 1 1
link "${PREV}"
restart
want on_previous "$(current)" "${PREV}"
want prev_read "$(code ${LOCAL}/os/goals?limit=1)" 200
want prev_ignores_settings "$(code ${REMOTE}/os/goals?limit=1)" 200
dbok
echo "RETURN_SECONDS $(($(date +%s) - T_A))"
T_B=$(date +%s)
link "${NEW}"
conf enforced enforced 1 1 1
restart
want on_new "$(appsha)" "${APP_SHA}"
want stranger_again "$(code ${REMOTE}/os/goals?limit=1)" 401
want owner_again "$(authed READ ${REMOTE}/os/goals?limit=1)" 200
want router_again "$(code ${LOCAL}/os/goals?limit=1)" 200
want tokens_survived "$(sudo -n stat -c '%U %a' ${ENVF})" "root 600"
dbok
echo "FORWARD_SECONDS $(($(date +%s) - T_B))"
finish B5_ROLLBACK b5.pass
""")
SCRIPTS["b6_final_ro.sh"] = ("B6 read-only final state", r"""
want app_sha "$(appsha)" "${APP_SHA}"
want current "$(sudo -n readlink -f ${BASE}/current)" "${BASE}/releases/${RID}"
want gateway "$(pid ${GW})" ${GW0}
want gate_active "$(systemctl show ${GATE} -p ActiveState --value)" active
want budget "$(budget)" "True OK 3 5 True"
want ledger "$(ledger)" "${LG0}"
dbok; forget
want no_failed_units "$(systemctl list-units --failed --no-legend | wc -l)" 0
want stranger "$(code ${REMOTE}/os/goals?limit=1)" 401
want token_in_journal "$(sudo -n bash -c "journalctl -u ${API} --since '-2 hours' -o cat --no-pager | grep -cFf <(sed -n 's/^[A-Z_]*=//p' ${ENVF})")" 0
want dropin_mode "$(sudo -n stat -c '%U %a' ${F})" "root 644"
sudo -n grep -cE 'TOKEN' ${F} | grep -qx 0 && echo OK_no_token_in_dropin || fail token_in_dropin
for u in lilith-memory-broker lilith-authority-dev lilith-recovery-witness; do echo "SVC ${u} $(systemctl show ${u} -p ActiveState,MainPID,NRestarts | LC_ALL=C sort | paste -sd' ')"; done
finish B6_FINAL
""")
SCRIPTS["rb_restore_previous.sh"] = ("RB recovery after the merge: the known-good release, by the same relink and restart as the deploy helper's own rollback", r"""
PREV=$(sudo -n cat ${W}/prev 2>/dev/null || true); PSHA=$(sudo -n cat ${W}/prevsha 2>/dev/null || true)
[ -n "${PREV}" ] && [ -n "${PSHA}" ] && sudo -n test -f "${PREV}/app.py" || { echo "RB_ABORTED no recorded previous release"; exit 3; }
conf open-acknowledged open-acknowledged 0 0 0
[ "$(current)" = "${PREV}" ] || link "${PREV}"
restart
want on_previous "$(current)" "${PREV}"
want previous_app "$(appsha)" "${PSHA}"
want local_read "$(code ${LOCAL}/os/goals?limit=1)" 200
want remote_read "$(code ${REMOTE}/os/goals?limit=1)" 200
want gateway "$(pid ${GW})" ${GW0}
want gate_active "$(systemctl show ${GATE} -p ActiveState --value)" active
dbok; forget
finish RB_RESTORE
""")
SCRIPTS["m1_model_turns.sh"] = ("M1 two model requests, budget 3 to 5, no reset, no retry", SEND + r"""
sudo -n test -f ${W}/b5.pass || { echo "M1_ABORTED B5 did not pass"; exit 3; }
sudo -n test ! -e ${W}/m1.started || { echo "M1_ABORTED already ran"; exit 3; }
want budget_before "$(budget)" "True OK 3 5 True"
[ -z "${FAILS}" ] || { echo "M1_MODEL FAIL:${FAILS}"; exit 1; }
sudo -n touch ${W}/m1.started
T0=$(date -u '+%Y-%m-%d %H:%M:%S')
SES=auth-model-20261101
R1=$(send "TEST_ONLY hey how are you" ${SES}-t1); echo "T1 ${R1}"; sleep 2
R2=$(send "TEST_ONLY what are my options for application 14?" ${SES}-t2); echo "T2 ${R2}"; sleep 3
want t1_status "$(echo "${R1}" | cut -d' ' -f2,3)" "200 completed"
want t2_status "$(echo "${R2}" | cut -d' ' -f2,3)" "200 completed"
[ "$(echo "${R1}" | cut -d' ' -f4)" -gt 0 ] && [ "$(echo "${R2}" | cut -d' ' -f4)" -gt 0 ] && echo OK_replies_not_empty || fail empty_reply
want budget_after "$(hf "$(curl -s -m 5 http://127.0.0.1:9911/healthz)" budget_used budget_requests)" "5 5"
want forwarded "$(sudo -n journalctl --namespace=${NS} -u ${GATE} --since "${T0}" --no-pager -o cat | grep -c '"decision": "FORWARDED"')" 2
dbok
finish M1_MODEL m1.pass
""")
SCRIPTS["status_ro.sh"] = ("status probe", r"""
echo "MARKERS $(sudo -n find ${W} -mindepth 1 -maxdepth 1 -printf '%f@ ' 2>/dev/null)"
echo "GATE $(systemctl show ${GATE} -p ActiveState,MainPID | LC_ALL=C sort | paste -sd' ')"
echo "API $(systemctl show ${API} -p ActiveState,MainPID | LC_ALL=C sort | paste -sd' ')"
echo "WINDOW_SCRIPTS_RUNNING $(pgrep -fc 'auth[-]window' || true)"
""")
for name, (title, body) in SCRIPTS.items():
    text = COMMON.replace("%(title)s", title).replace("%%", "%") + body.lstrip("\n")
    assert len(text.encode()) < 26000, name
    (S / name).write_bytes(text.encode("ascii"))
    print("OK", name, len(text))
for n in ("drive_auth.py",):
    shutil.copy2(Path(__file__).with_name(n), S / n)
shutil.copy2(e1 / "scripts/dread.py", S / "dread.py")
prior = pkg / "tests" / "prior"; prior.mkdir(parents=True, exist_ok=True)
for n in ("a0_preflight_ro.sh", "a1_dropin_open.sh", "ra_remove_dropin.sh", "b0_verify_deploy_ro.sh", "b1_tokens.sh"):      # already ran on DEV; kept only to build the simulation's starting state
    shutil.move(str(S / n), str(prior / n))
(pkg / "auth.conf.template").write_bytes(b"[Service]\nEnvironment=\"LILITH_OS_WRITE_AUTH=open-acknowledged\"\nEnvironment=\"LILITH_OS_READ_AUTH=open-acknowledged\"\n")
