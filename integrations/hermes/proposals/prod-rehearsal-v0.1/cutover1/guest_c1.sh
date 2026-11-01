set -u
# Cutover 1 stages, as root on lilith-01 only, from /var/tmp/c1 (PREPARED, NOT APPROVED, NOT RUN). Tokens are never printed or passed on a command line. Prints names, counts, digests and verdicts, never content.
#   bash guest_c1.sh w0 p0|pre  w1  w2  w3  w4  w5  rb  status
# Touches only app.py (through deploy.yml), one drop-in, one token file and its own working directory. Never the router, Hermes, persona, or a database.
STAGE=${1:-}; ARG=${2:-}
ROOT=${C1_ROOT:-}                       # the simulation sets this; empty on the host
HOST_NAME=lilith-01
HH=${ROOT}/home/lilith/.hermes
APP=${HH}/lilith-os/api/app.py
PY=${C1_PY:-${HH}/lilith-os/api-venv/bin/python}
API=lilith-os-api.service
GW=hermes-gateway.service
D=${ROOT}/etc/systemd/system/${API}.d
F=${D}/auth.conf
ENVD=${ROOT}/etc/lilith-os-api
ENVF=${ENVD}/auth.env
W=${ROOT}/root/cutover1-20261101
IN=${ROOT}/var/tmp/c1
NIC=${C1_NIC:-10.20.0.2}
LOCAL=http://127.0.0.1:8765
REMOTE=http://${NIC}:8765
OLD_SHA=bb0a4139641c0a81607263b07fa854deb34241b5fcfcdcab965c6a82dd8826d3
NEW_SHA=53dfae2aed84004c8ef2f24a4a07003b3864d700cba6e7eeaeb2bee8e20f44d2
SOUL_SHA=d082db5aa1a8745460c1c3a3edebaf6fcd196336f5e1a5e8ef7108303bda5ccd
USER_SHA=6d7804efb32b158105e017e38857abc09ea6c44b5fb6f39636840c290b792d9c
FAILS=
fail() { echo "CHECK_FAIL $1"; FAILS="${FAILS} $1"; }
want() { [ "$2" = "$3" ] && echo "OK $1 $2" || fail "$1(got_$2_want_$3)"; }
pid() { systemctl show "$1" -p MainPID --value; }
sha() { sha256sum "$1" 2>/dev/null | cut -c1-64; }
code() { curl -s -o /dev/null -m 10 -w '%{http_code}' "$@"; }
authed() {   # authed WRITE|READ url [curl args]: the header goes in on stdin
  local name=LILITH_OS_$1_TOKEN hdr=X-LILITH-OS-Read url=$2; shift 2
  [ "${name}" = LILITH_OS_WRITE_TOKEN ] && hdr=X-LILITH-OS-Write
  printf 'header = "%s: %s"\n' "${hdr}" "$(sed -n "s/^${name}=//p" "${ENVF}")" | curl -s -o /dev/null -m 10 -w '%{http_code}' -K - "$@" "${url}"
}
conf() {   # conf WRITE READ focus trust envfile: the whole drop-in, written atomically
  mkdir -p "${D}"
  { echo "[Service]"; echo "Environment=\"LILITH_OS_WRITE_AUTH=$1\""; echo "Environment=\"LILITH_OS_READ_AUTH=$2\""
    [ "$3" = 1 ] && echo "Environment=\"LILITH_OS_FOCUS_READ_ONLY=1\""
    [ "$4" = 1 ] && echo "Environment=\"LILITH_OS_TRUST_LOOPBACK=1\""
    [ "$5" = 1 ] && echo "EnvironmentFile=/etc/lilith-os-api/auth.env"; } > "${F}.new"
  chmod 0644 "${F}.new"; mv -f "${F}.new" "${F}"; systemctl daemon-reload
}
health() { for _ in $(seq 1 30); do [ "$(code ${LOCAL}/health)" = 200 ] && return 0; sleep 1; done; return 1; }
restart() { systemctl restart ${API}; health || fail api_not_healthy; }
base() { ${C1_AS:-runuser -u lilith --} "${PY}" -I -B "${IN}/live_compare.py" baseline "${HH}" > "$1.new" && mv -f "$1.new" "$1" || fail "baseline_$(basename "$1")"; }
settings() { find "${HH}" -maxdepth 4 \( -name router.yaml -o -name config.yaml \) -not -path '*/hermes-agent/*' -not -path '*venv*' | LC_ALL=C sort | while read -r x; do echo "$(sha "${x}") ${x}"; done; }
failed() { systemctl --failed --plain --no-legend | awk '{print $1}' | LC_ALL=C sort; }
data() {   # data <post>: anything that differs must have moved on its own before the window
  local pairs=
  [ -f "${W}/p0.json" ] && pairs="${W}/p0.json ${W}/pre.json"
  # shellcheck disable=SC2086
  "${PY}" -I -B "${IN}/live_compare.py" judge "${W}/pre.json" "$1" ${pairs} "${W}/pre.json" "${W}/pre2.json" > "${W}/judge.out" 2>&1 && echo OK_data || fail data
  sed -n 's/^\(JUDGE_EQUAL\|UNEXPECTED\|MOVED\)/\1/p' "${W}/judge.out"
}
finish() { echo "T1 $(date -u +%FT%TZ)"; if [ -z "${FAILS}" ]; then [ -n "${2:-}" ] && touch "${W}/$2"; echo "$1 PASS"; else echo "$1 FAIL:${FAILS}"; exit 1; fi; }
need() { [ -f "${W}/$1" ] || { echo "$2_ABORTED $1 is missing"; exit 3; }; }

echo "HOST $(hostname) STAGE ${STAGE} ${ARG} T0 $(date -u +%FT%TZ)"
[ -n "${ROOT}" ] || [ "$(hostname)" = "${HOST_NAME}" ] || { echo "WRONG_HOST"; exit 3; }
[ "$(id -u)" = 0 ] || { echo "WRONG_HOST needs root"; exit 3; }
install -d -m 0700 "${W}"

case "${STAGE}" in
w0)   # Read-only on LILITH. p0 is the review ahead of the window; pre opens the window and needs p0.
  [ "${ARG}" = p0 ] || [ "${ARG}" = pre ] || { echo "W0_ABORTED argument"; exit 3; }
  [ "${ARG}" = p0 ] || [ -f "${W}/p0.json" ] || { echo "W0_ABORTED p0 did not run"; exit 3; }
  [ ! -e "${W}/w0.${ARG}.pass" ] || { echo "W0_ABORTED already ran"; exit 3; }
  want app "$(sha "${APP}")" "${OLD_SHA}"
  want soul "$(sha "${HH}/SOUL.md")" "${SOUL_SHA}"
  want user "$(sha "${HH}/memories/USER.md")" "${USER_SHA}"
  want api_active "$(systemctl is-active ${API})" active
  want gateway_active "$(systemctl is-active ${GW})" active
  want no_auth_dropin "$([ -e "${F}" ] && echo present || echo absent)" absent
  want no_token_file "$([ -e "${ENVF}" ] && echo present || echo absent)" absent
  want no_auth_settings "$(systemctl show ${API} -p Environment --value | grep -c 'LILITH_OS_')" 0
  echo "DROPINS $(systemctl show ${API} -p DropInPaths --value)"
  want read_open "$(code "${REMOTE}/os/goals?limit=1")" 200
  want disk_room "$([ "$(df -Pm "${HH}" | awk 'NR==2{print $4}')" -gt 1024 ] && echo yes || echo no)" yes
  settings > "${W}/settings.${ARG}"; [ -s "${W}/settings.${ARG}" ] && echo "SETTINGS_FILES $(wc -l < "${W}/settings.${ARG}")" || fail no_settings_found
  if [ "${ARG}" = p0 ]; then
    base "${W}/p0.json"; failed > "${W}/failed.p0"; echo "FAILED_UNITS $(wc -l < "${W}/failed.p0")"
    finish W0 w0.p0.pass
  fi
  want settings_unchanged "$(sha "${W}/settings.pre")" "$(sha "${W}/settings.p0")"
  base "${W}/pre.json"
  sleep "${C1_TICK:-130}"
  base "${W}/pre2.json"
  failed > "${W}/failed.pre"; pid ${GW} > "${W}/gateway.pid"; date -u '+%F %T' > "${W}/t0"
  echo "BASELINE $(sha "${W}/pre.json" | cut -c1-16) CONTROL $(sha "${W}/pre2.json" | cut -c1-16)"
  finish W0 w0.pre.pass;;
w1)   # Tokens and the open drop-in. The running code ignores both, so no restart.
  need w0.pre.pass W1
  [ ! -e "${ENVF}" ] || { echo "W1_ABORTED token file exists"; exit 3; }
  install -d -m 0700 "${ENVD}"
  "${PY}" -I -c 'import os, secrets, sys; f=os.open(sys.argv[1], os.O_WRONLY|os.O_CREAT|os.O_EXCL, 0o600); os.write(f, ("LILITH_OS_READ_TOKEN=%s\nLILITH_OS_WRITE_TOKEN=%s\n" % (secrets.token_hex(32), secrets.token_hex(32))).encode()); os.close(f)' "${ENVF}"
  want token_file "$(stat -c '%a' "${ENVF}")" 600
  conf open-acknowledged open-acknowledged 0 1 1
  want read_still_open "$(code "${LOCAL}/os/goals?limit=1")" 200
  finish W1 w1.pass;;
w2)   # After deploy.yml: the new code, still open.
  need w1.pass W2
  want app "$(sha "${APP}")" "${NEW_SHA}"
  B=$(ls -t "${APP}".bak.gitdeploy.* 2>/dev/null | head -1)
  want backup "$(sha "${B}")" "${OLD_SHA}"
  echo "${B}" > "${W}/backup"
  want local_read "$(code "${LOCAL}/os/goals?limit=1")" 200
  want remote_read "$(code "${REMOTE}/os/goals?limit=1")" 200
  finish W2 w2.pass;;
w3)   # Enforce writes.
  need w2.pass W3
  conf enforced open-acknowledged 0 1 1
  restart
  for p in goals tasks drafts; do want "stranger_write ${p}" "$(code -X POST -H 'content-type: application/json' -d '{}' ${REMOTE}/os/${p})" 401; done
  C=$(authed WRITE ${REMOTE}/os/goals -X POST -H 'content-type: application/json' -d '{}')
  [ "${C}" = 400 ] || [ "${C}" = 422 ] && echo "OK owner_write_reaches_validation ${C}" || fail "owner_write(${C})"
  C=$(code -X POST -H 'content-type: application/json' -d '{}' ${LOCAL}/os/goals)
  [ "${C}" = 400 ] || [ "${C}" = 422 ] && echo "OK router_write_reaches_validation ${C}" || fail "router_write(${C})"
  finish W3 w3.pass;;
w4)   # Enforce reads and focus read-only.
  need w3.pass W4
  conf enforced enforced 1 1 1
  restart
  for p in '/os/goals?limit=1' /os/goals/focus '/os/tasks?limit=1' '/os/drafts?limit=1' /os/world /memory/overview /career/pipeline /audit/recent /system/status /docs /openapi.json; do
    want "stranger ${p}" "$(code ${REMOTE}${p})" 401
  done
  want wrong_token "$(code -H 'X-LILITH-OS-Read: wrong' "${REMOTE}/os/goals?limit=1")" 401
  want stranger_conversation "$(code -X POST -H 'content-type: application/json' -d '{"message":"x"}' ${REMOTE}/os/conversation)" 401
  want local_conversation_needs_credential "$(code -X POST -H 'content-type: application/json' -d '{"message":"x"}' ${LOCAL}/os/conversation)" 401
  want owner_read "$(authed READ "${REMOTE}/os/goals?limit=1")" 200
  for p in '/os/goals?limit=200' /os/goals/focus '/os/tasks?limit=200' '/os/drafts?limit=200' /os/world; do want "router_read ${p}" "$(code "${LOCAL}${p}")" 200; done
  want health_open "$(code ${REMOTE}/health)" 200
  finish W4 w4.pass;;
w5)   # Read-only: nothing else moved.
  need w4.pass W5
  sleep "${C1_TICK:-130}"
  base "${W}/post.json"; data "${W}/post.json"
  want soul "$(sha "${HH}/SOUL.md")" "${SOUL_SHA}"
  want user "$(sha "${HH}/memories/USER.md")" "${USER_SHA}"
  want gateway_untouched "$(pid ${GW})" "$(cat "${W}/gateway.pid")"
  want settings_unchanged "$(settings | sha256sum | cut -c1-64)" "$(sha256sum < "${W}/settings.pre" | cut -c1-64)"
  want no_new_failed_units "$(failed | LC_ALL=C comm -13 "${W}/failed.pre" - | wc -l)" 0
  J=$(journalctl --utc -u ${API} --since "$(cat "${W}/t0")" --no-pager 2>/dev/null)
  [ -n "${J}" ] && echo OK_journal_read || fail journal_empty
  want no_token_in_journal "$(printf '%s
' "${J}" | grep -cFf <(sed -n 's/^[^=]*=//p' "${ENVF}"))" 0
  unset J
  want tokens_root_only "$(stat -c '%a' "${ENVF}")" 600
  finish W5 w5.pass;;
rb)   # The app.py return: previous code, open, same data. Works from any stage after w1.
  [ -f "${W}/w0.pre.pass" ] || { echo "RB_ABORTED the window never started"; exit 3; }
  T_A=$(date +%s)
  conf open-acknowledged open-acknowledged 0 0 0
  if [ "$(sha "${APP}")" != "${OLD_SHA}" ]; then
    B=$(cat "${W}/backup" 2>/dev/null || ls -t "${APP}".bak.gitdeploy.* 2>/dev/null | head -1)
    [ "$(sha "${B}")" = "${OLD_SHA}" ] || { echo "RB_RESTORE FAIL: no backup of the previous code"; exit 1; }
    install -o "${C1_OWNER:-lilith}" -g "${C1_OWNER:-lilith}" -m 700 "${B}" "${APP}"
  fi
  restart
  want on_previous "$(sha "${APP}")" "${OLD_SHA}"
  want local_read "$(code "${LOCAL}/os/goals?limit=1")" 200
  want remote_read "$(code "${REMOTE}/os/goals?limit=1")" 200
  echo "RETURN_SECONDS $(($(date +%s) - T_A))"
  want gateway_active "$(systemctl is-active ${GW})" active
  base "${W}/rb.json"; data "${W}/rb.json"
  finish RB_RESTORE rb.pass;;
status)
  echo "MARKERS $(find "${W}" -mindepth 1 -maxdepth 1 -name '*.pass' -printf '%f@ ' 2>/dev/null)"
  echo "GATE $(systemctl show ${GW} -p ActiveState,MainPID | LC_ALL=C sort | paste -sd' ')"
  echo "API $(systemctl show ${API} -p ActiveState,MainPID | LC_ALL=C sort | paste -sd' ')"
  RUNNING=0
  for q in $(pgrep -f 'guest[_]c1' || true); do
    [ "${q}" = "$$" ] && continue
    c=$(tr '\0' ' ' < "/proc/${q}/cmdline" 2>/dev/null) || continue
    case "${c}" in *" status"*|"") ;; *) RUNNING=$((RUNNING + 1));; esac
  done
  echo "WINDOW_SCRIPTS_RUNNING ${RUNNING}";;
*) echo "UNKNOWN_STAGE"; exit 3;;
esac
