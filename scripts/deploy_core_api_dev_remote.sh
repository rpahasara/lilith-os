#!/usr/bin/env bash
set -Eeuo pipefail

CANDIDATE_BUNDLE="${1:?candidate bundle path required}"
CANDIDATE_ATTESTATION="${2:?candidate attestation path required}"
CANDIDATE_SHA="${3:?candidate SHA required}"
TRUSTED_VERIFIER="${4:?trusted verifier path required}"
TRUSTED_DURABILITY_PROBE="${5:?trusted durability probe path required}"

APP_USER="lilith"
APP_GROUP="lilith"
APP_ROOT="/home/lilith/.hermes/lilith-os-dev"
RELEASES_DIR="${APP_ROOT}/releases"
CURRENT_LINK="${APP_ROOT}/current"
VENV_DIR="${APP_ROOT}/api-venv"
SERVICE_NAME="lilith-os-api-dev.service"
HEALTH_URL="http://127.0.0.1:8765/health"

if [[ ! "${CANDIDATE_SHA}" =~ ^[0-9a-f]{40}$ ]]; then
  echo "Candidate SHA is invalid." >&2
  exit 2
fi

RELEASE_DIR="${RELEASES_DIR}/${CANDIDATE_SHA}"
STAGING_DIR="${RELEASES_DIR}/.${CANDIDATE_SHA}.staging.$$"
PREVIOUS_RELEASE=""
PROBE_PREPARED=0
if [[ -L "${CURRENT_LINK}" ]]; then
  PREVIOUS_RELEASE="$(readlink -f "${CURRENT_LINK}")"
fi

rollback() {
  echo "--- DEV BUNDLE ROLLBACK ---"
  if [[ -n "${PREVIOUS_RELEASE}" && -d "${PREVIOUS_RELEASE}" ]]; then
    local rollback_link="${APP_ROOT}/.current.rollback.$$"
    ln -s "${PREVIOUS_RELEASE}" "${rollback_link}"
    mv -Tf "${rollback_link}" "${CURRENT_LINK}"
    systemctl restart "${SERVICE_NAME}" || true
    sleep 3
    curl -fsS "${HEALTH_URL}" || true
    echo
  else
    systemctl stop "${SERVICE_NAME}" || true
  fi
}

cleanup() {
  if [[ "${PROBE_PREPARED}" == "1" && -f "${TRUSTED_DURABILITY_PROBE}" ]]; then
    runuser -u "${APP_USER}" -- env PYTHONDONTWRITEBYTECODE=1 \
      "${VENV_DIR}/bin/python" "${TRUSTED_DURABILITY_PROBE}" cleanup \
      --candidate-sha "${CANDIDATE_SHA}" || true
  fi
  rm -f \
    "${CANDIDATE_BUNDLE}" \
    "${CANDIDATE_ATTESTATION}" \
    "${TRUSTED_VERIFIER}" \
    "${TRUSTED_DURABILITY_PROBE}" \
    "$0" || true
  if [[ -d "${STAGING_DIR}" ]]; then
    rm -rf --one-file-system "${STAGING_DIR}" || true
  fi
}
trap cleanup EXIT

echo "--- VERIFY DEV RUNTIME ---"
test -x "${VENV_DIR}/bin/python"
test -d "${RELEASES_DIR}"
test -f "${CANDIDATE_BUNDLE}"
test -f "${CANDIDATE_ATTESTATION}"
test -f "${TRUSTED_VERIFIER}"
test -f "${TRUSTED_DURABILITY_PROBE}"

echo "--- VERIFY AND EXTRACT EXACT-SHA BUNDLE ---"
install -d -o "${APP_USER}" -g "${APP_GROUP}" -m 700 "${STAGING_DIR}"
"${VENV_DIR}/bin/python" "${TRUSTED_VERIFIER}" \
  --archive "${CANDIDATE_BUNDLE}" \
  --attestation "${CANDIDATE_ATTESTATION}" \
  --destination "${STAGING_DIR}" \
  --expected-sha "${CANDIDATE_SHA}"

echo "--- PRE-INSTALL VALIDATION ---"
test "$("${VENV_DIR}/bin/python" -c 'import json,sys; print(json.load(open(sys.argv[1], encoding="utf-8"))["candidateSha"])' "${STAGING_DIR}/deployment-manifest.json")" = "${CANDIDATE_SHA}"
"${VENV_DIR}/bin/python" -m compileall -q "${STAGING_DIR}/app.py" "${STAGING_DIR}/lilith_memory"

echo "--- INSTALL DEV PYTHON DEPENDENCIES ---"
"${VENV_DIR}/bin/python" -m pip install \
  --disable-pip-version-check \
  -r "${STAGING_DIR}/requirements.txt"

echo "--- RUN ISOLATED DEV SYNTHETIC TESTS ---"
runuser -u "${APP_USER}" -- env \
  LILITH_ENV=test \
  PYTHONDONTWRITEBYTECODE=1 \
  "${VENV_DIR}/bin/python" -m unittest discover \
  -s "${STAGING_DIR}/tests" -p 'test_*.py'

if [[ -d "${RELEASE_DIR}" ]]; then
  echo "--- VERIFY EXISTING IMMUTABLE RELEASE ---"
  cmp -s "${STAGING_DIR}/deployment-manifest.json" "${RELEASE_DIR}/deployment-manifest.json"
  cmp -s "${STAGING_DIR}/.bundle-sha256" "${RELEASE_DIR}/.bundle-sha256"
  rm -rf --one-file-system "${STAGING_DIR}"
else
  chown -R "${APP_USER}:${APP_GROUP}" "${STAGING_DIR}"
  find "${STAGING_DIR}" -type d -exec chmod 750 {} +
  find "${STAGING_DIR}" -type f -exec chmod 640 {} +
  mv "${STAGING_DIR}" "${RELEASE_DIR}"
fi

echo "--- ATOMIC DEV RELEASE SWITCH ---"
NEXT_LINK="${APP_ROOT}/.current.${CANDIDATE_SHA}.$$"
ln -s "${RELEASE_DIR}" "${NEXT_LINK}"
mv -Tf "${NEXT_LINK}" "${CURRENT_LINK}"
chown -h "${APP_USER}:${APP_GROUP}" "${CURRENT_LINK}"

echo "--- PREPARE PERSISTENT DEV CANONICAL DURABILITY PROBE ---"
PRE_RESTART_PID="$(systemctl show --property=MainPID --value "${SERVICE_NAME}")"
if [[ ! "${PRE_RESTART_PID}" =~ ^[1-9][0-9]*$ ]]; then
  echo "DEV service has no pre-restart PID." >&2
  rollback
  exit 1
fi
systemctl show "${SERVICE_NAME}" \
  --property=MainPID,NRestarts,ActiveState,SubState,ActiveEnterTimestamp \
  --no-pager
runuser -u "${APP_USER}" -- env \
  LILITH_ENV=dev \
  PYTHONDONTWRITEBYTECODE=1 \
  "${VENV_DIR}/bin/python" "${TRUSTED_DURABILITY_PROBE}" prepare \
  --candidate-sha "${CANDIDATE_SHA}" \
  --pre-restart-pid "${PRE_RESTART_PID}"
PROBE_PREPARED=1

echo "--- ENABLE AND RESTART DEV SERVICE ---"
systemctl enable "${SERVICE_NAME}"
if ! systemctl restart "${SERVICE_NAME}"; then
  echo "DEV service restart failed." >&2
  rollback
  exit 1
fi
sleep 3

echo "--- VERIFY DEV SERVICE AND HEALTH ---"
if ! systemctl is-active --quiet "${SERVICE_NAME}"; then
  systemctl status "${SERVICE_NAME}" --no-pager -l || true
  journalctl -u "${SERVICE_NAME}" -n 50 --no-pager || true
  rollback
  exit 1
fi
if ! curl -fsS "${HEALTH_URL}"; then
  echo
  journalctl -u "${SERVICE_NAME}" -n 50 --no-pager || true
  rollback
  exit 1
fi
echo

POST_RESTART_PID="$(systemctl show --property=MainPID --value "${SERVICE_NAME}")"
if [[ ! "${POST_RESTART_PID}" =~ ^[1-9][0-9]*$ || "${POST_RESTART_PID}" == "${PRE_RESTART_PID}" ]]; then
  echo "DEV service restart did not establish a new process." >&2
  rollback
  exit 1
fi
systemctl show "${SERVICE_NAME}" \
  --property=MainPID,NRestarts,ActiveState,SubState,ActiveEnterTimestamp \
  --no-pager

echo "--- VERIFY PERSISTENT DEV CANONICAL DURABILITY IN NEW PROCESS ---"
runuser -u "${APP_USER}" -- env \
  LILITH_ENV=dev \
  PYTHONDONTWRITEBYTECODE=1 \
  "${VENV_DIR}/bin/python" "${TRUSTED_DURABILITY_PROBE}" verify \
  --candidate-sha "${CANDIDATE_SHA}" \
  --post-restart-pid "${POST_RESTART_PID}"

echo "--- CLEAN UP SYNTHETIC DEV DURABILITY ENVIRONMENT ---"
runuser -u "${APP_USER}" -- env PYTHONDONTWRITEBYTECODE=1 \
  "${VENV_DIR}/bin/python" "${TRUSTED_DURABILITY_PROBE}" cleanup \
  --candidate-sha "${CANDIDATE_SHA}"
PROBE_PREPARED=0

echo "--- POST-INSTALL IDENTITY READBACK ---"
test "$(readlink -f "${CURRENT_LINK}")" = "${RELEASE_DIR}"
test "$("${VENV_DIR}/bin/python" -c 'import json,sys; print(json.load(open(sys.argv[1], encoding="utf-8"))["candidateSha"])' "${CURRENT_LINK}/deployment-manifest.json")" = "${CANDIDATE_SHA}"
cat "${CURRENT_LINK}/deployment-manifest.json"
cat "${CURRENT_LINK}/.bundle-sha256"

echo "--- DEV DEPLOYMENT COMPLETE ---"
