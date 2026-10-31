set -u
# Runs as root on lilith-rehearsal-01 only, from files placed in /var/tmp/g3. Stages R3 to R9 of the rehearsal runbook. Prints names, counts, digests and verdicts, never content.
#   bash guest_rehearsal.sh SYNTHETIC|REAL
# SYNTHETIC builds a small tree on the blank disk and proves the flow with no real data. REAL reads the attached copy, read-only.
MODE=${1:-}
ROOT=${G3_ROOT:-}                       # the simulation sets this; empty on the VM
HOST_NAME=lilith-rehearsal-01
IN=${ROOT}/var/tmp/g3
W=${ROOT}/srv/rehearsal
MNT=${ROOT}/mnt/g3-source
TREE=${W}/tree
LINK=${ROOT}/home/lilith/.hermes
EVID=${W}/evidence
PY=${G3_PY:-python3}
OLD_SHA=bb0a4139641c0a81607263b07fa854deb34241b5fcfcdcab965c6a82dd8826d3
NEW_SHA=53dfae2aed84004c8ef2f24a4a07003b3864d700cba6e7eeaeb2bee8e20f44d2
PORT=8765
NIC=$(hostname -I | awk '{print $1}')
FAILS=
fail() { echo "CHECK_FAIL $1"; FAILS="${FAILS} $1"; }
stop() { echo "REHEARSAL STOPPED: $1"; api_stop; [ -n "${ROOT}" ] || umount "${MNT}" 2>/dev/null; exit 1; }
want() { [ "$2" = "$3" ] && echo "OK $1 $2" || stop "$1(got_$2_want_$3)"; }
code() { curl -s -o /dev/null -m 10 -w '%{http_code}' "$@"; }
SERVER=
api_stop() { if [ -n "${SERVER}" ]; then kill "${SERVER}" 2>/dev/null; wait "${SERVER}" 2>/dev/null; SERVER=; fi; }
api_start() {   # api_start KEY=VALUE ...: the copied venv, the copied code, the copied data
  api_stop
  ( cd "${TREE}/lilith-os/api" && exec env -i PATH=/usr/bin:/bin HOME="${ROOT}/home/lilith" "$@" ${G3_API:-${TREE}/lilith-os/api-venv/bin/python -m uvicorn app:app --host 0.0.0.0 --port ${PORT} --log-level warning} >> "${EVID}/api.log" 2>&1 ) &
  SERVER=$!
  for _ in $(seq 1 60); do [ "$(code http://127.0.0.1:${PORT}/health)" = 200 ] && return 0; sleep 1; done
  stop api_not_healthy
}
checkpoint() {  # folds each WAL into its database, so a digest sees all of it. Works on the working copy only.
  for f in "${TREE}/state.db" "${TREE}"/lilith-os/data/*.db; do
    [ -f "${f}" ] && ${PY} -I -c 'import sqlite3,sys; c=sqlite3.connect(sys.argv[1]); c.execute("PRAGMA wal_checkpoint(TRUNCATE)"); c.close()' "${f}"
  done
  rm -f "${TREE}"/*-wal "${TREE}"/*-shm "${TREE}"/lilith-os/data/*-wal "${TREE}"/lilith-os/data/*-shm
}
snap() { checkpoint; ${PY} -I -B "${IN}/rehearsal_compare.py" baseline "${TREE}" "${EVID}/$1.json" >/dev/null || stop "baseline_$1"; }
diffs() { ${PY} -I -B "${IN}/rehearsal_compare.py" compare "${EVID}/$1.json" "${EVID}/$2.json"; }
ROUTES='/os/goals?limit=200 /os/goals/focus /os/tasks?limit=200 /os/drafts?limit=200 /os/world'
echo "HOST $(hostname) MODE ${MODE} T0 $(date -u +%FT%TZ)"
[ "${MODE}" = SYNTHETIC ] || [ "${MODE}" = REAL ] || { echo "REHEARSAL STOPPED: mode"; exit 1; }
[ -n "${ROOT}" ] || [ "$(hostname)" = "${HOST_NAME}" ] || { echo "REHEARSAL STOPPED: wrong host"; exit 1; }
[ -n "${ROOT}" ] || [ "$(id -u)" = 0 ] || { echo "REHEARSAL STOPPED: needs root"; exit 1; }

echo "== guards"
if [ -z "${ROOT}" ]; then
  bash "${IN}/guest_dns_check.sh" | grep -qx 'DNS_CHECK PASS' && echo OK_dns_guard || stop dns_guard_not_active
  [ "$(code -H 'Metadata-Flavor: Google' http://169.254.169.254/computeMetadata/v1/instance/service-accounts/default/token)" = 404 ] && echo OK_no_token || stop token_present
fi
[ ! -e "${W}/started" ] || stop "already ran: destroy the working tree first"
mkdir -p "${W}" "${EVID}" "${MNT}" "$(dirname "${LINK}")"; chmod 700 "${W}"; touch "${W}/started"

echo "== R3 source, read-only"
if [ "${MODE}" = SYNTHETIC ]; then
  DEV=/dev/disk/by-id/google-synthetic
  if [ -z "${ROOT}" ]; then mkfs.ext4 -q -F "${DEV}"; mount "${DEV}" "${MNT}" || stop mount_synth; fi
  S=${MNT}/home/lilith/.hermes
  mkdir -p "${S}/memories" "${S}/lilith-os/data" "${S}/lilith-os/api"
  echo TEST_ONLY > "${S}/SOUL.md"; echo TEST_ONLY > "${S}/memories/USER.md"; echo x > "${S}/.env"; echo x > "${S}/lilith-os/data/actor_authority.key"
  for f in state.db lilith-os/data/lilith.db lilith-os/data/cognitive_memory.db lilith-os/data/privacy_governance.db; do
    ${PY} -I -c 'import sqlite3,sys; c=sqlite3.connect(sys.argv[1]); c.execute("PRAGMA journal_mode=WAL"); c.execute("CREATE TABLE t (a)"); c.execute("INSERT INTO t VALUES (1)"); c.commit(); c.close()' "${S}/${f}"
  done
  cp "${IN}/app_old.py" "${S}/lilith-os/api/app.py"
  if [ -z "${ROOT}" ]; then umount "${MNT}"; mount -o ro,noload "${DEV}" "${MNT}" || stop mount_synth_ro; fi
else
  DEV=/dev/disk/by-id/google-copy-part1
  [ -b "${DEV}" ] || stop no_copy_disk
  mount -o ro,noload "${DEV}" "${MNT}" || stop mount_copy
  S=${MNT}/home/lilith/.hermes
fi
if [ -z "${ROOT}" ]; then touch "${MNT}/write-test" 2>/dev/null && stop source_is_writable; echo OK_source_read_only; fi

echo "== R4 allow-listed copy: nothing else leaves the source"
mkdir -p "${TREE}/memories" "${TREE}/lilith-os/data" "${TREE}/lilith-os/api"
cp -p "${S}/SOUL.md" "${TREE}/" || stop soul_missing
cp -p "${S}/memories/USER.md" "${TREE}/memories/" || stop user_missing
for f in state.db state.db-wal state.db-shm; do [ -f "${S}/${f}" ] && cp -p "${S}/${f}" "${TREE}/"; done
for d in lilith cognitive_memory privacy_governance; do
  for x in "" -wal -shm; do [ -f "${S}/lilith-os/data/${d}.db${x}" ] && cp -p "${S}/lilith-os/data/${d}.db${x}" "${TREE}/lilith-os/data/"; done
done
cp -p "${S}/lilith-os/api/app.py" "${TREE}/lilith-os/api/app.py"
[ "${MODE}" = REAL ] && { cp -a "${S}/lilith-os/api-venv" "${TREE}/lilith-os/api-venv" || stop venv; }
[ -n "${ROOT}" ] || umount "${MNT}"
echo "OK source_unmounted WAL_FILES $(ls "${TREE}"/*-wal "${TREE}"/lilith-os/data/*-wal 2>/dev/null | wc -l)"
CRED=$(${PY} -I -B "${IN}/rehearsal_compare.py" credentials "${TREE}" | grep -v site-packages)
[ "${CRED}" = NO_CREDENTIAL_NAMES ] && echo OK_no_credential_names || stop "credential_name_present $(echo "${CRED}" | wc -l)"
[ "${MODE}" = SYNTHETIC ] || want prod_app "$(sha256sum "${TREE}/lilith-os/api/app.py" | cut -c1-64)" "${OLD_SHA}"
cp -p "${TREE}/lilith-os/api/app.py" "${W}/app.previous"
rm -rf "${LINK}"; ln -s "${TREE}" "${LINK}"

echo "== R5 baseline"
snap b0
grep -c . "${EVID}/b0.json" >/dev/null
echo "BASELINE_DATABASES $(${PY} -I -c 'import json,sys; d=json.load(open(sys.argv[1])); print({k: sum(t["rows"] for t in v["tables"].values()) for k, v in d["databases"].items()}, d["missing"])' "${EVID}/b0.json")"
[ "${MODE}" = REAL ] || G3_API=${G3_API:-${PY} -I -B ${IN}/fake_core.py}

echo "== control: the current code, one maintenance tick"
api_start
sleep ${G3_TICK:-130}
for r in ${ROUTES}; do want "old_read ${r}" "$(code "http://127.0.0.1:${PORT}${r}")" 200; done
api_stop; snap b1
CONTROL=$(diffs b0 b1); [ "${CONTROL}" = COMPARE_EQUAL ] && echo OK_control_equal || echo "CONTROL_DIFFERS $(echo "${CONTROL}" | tr '\n' ' ')"

echo "== R6 target code and settings"
sha256sum "${IN}/app_new.py" | cut -c1-64 | grep -qx "${NEW_SHA}" || stop new_app_digest
cp "${IN}/app_new.py" "${TREE}/lilith-os/api/app.py"
RT=$(${PY} -I -c 'import secrets; print(secrets.token_hex(32))'); WT=$(${PY} -I -c 'import secrets; print(secrets.token_hex(32))')
ENFORCED="LILITH_OS_WRITE_AUTH=enforced LILITH_OS_READ_AUTH=enforced LILITH_OS_READ_TOKEN=${RT} LILITH_OS_WRITE_TOKEN=${WT} LILITH_OS_TRUST_LOOPBACK=1 LILITH_OS_FOCUS_READ_ONLY=1"
# shellcheck disable=SC2086
api_start ${ENFORCED}
sleep ${G3_TICK:-130}
for r in ${ROUTES}; do want "router_read ${r}" "$(code "http://127.0.0.1:${PORT}${r}")" 200; done
want stranger_read "$(code "http://${NIC}:${PORT}/os/goals?limit=1")" 401
want stranger_write "$(code -X POST -H 'content-type: application/json' -d '{}' "http://${NIC}:${PORT}/os/goals")" 401
want owner_read "$(printf 'header = "X-LILITH-OS-Read: %s"\n' "${RT}" | curl -s -o /dev/null -m 10 -w '%{http_code}' -K - "http://${NIC}:${PORT}/os/goals?limit=1")" 200
api_stop; snap b2

echo "== R7 compare"
AFTER=$(diffs b0 b2)
[ "${AFTER}" = "${CONTROL}" ] && echo "OK_same_as_control" || stop "new_code_differs_from_control"
[ "${AFTER}" = COMPARE_EQUAL ] && echo OK_rows_and_identity_equal

echo "== R9 rollback, timed"
T_A=$(date +%s)
cp -p "${W}/app.previous" "${TREE}/lilith-os/api/app.py"
api_start
RETURN=$(($(date +%s) - T_A))
want rollback_read "$(code "http://127.0.0.1:${PORT}/os/goals?limit=200")" 200
api_stop; snap b3
[ "$(diffs b0 b3)" = "${CONTROL}" ] && echo OK_rollback_equal || stop rollback_differs
echo "ROLLBACK_SECONDS ${RETURN}"
grep -cE "${RT}|${WT}" "${EVID}/api.log" | grep -qx 0 && echo OK_no_token_in_log || stop token_in_log
unset RT WT ENFORCED
echo "T1 $(date -u +%FT%TZ)"
echo "REHEARSAL PASS"
