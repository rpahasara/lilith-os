#!/usr/bin/env bash
set -Eeuo pipefail

CANDIDATE_APP="${1:?candidate app path required}"
CANDIDATE_REQ="${2:?candidate requirements path required}"

APP_USER="lilith"
APP_GROUP="lilith"

APP_ROOT="/home/lilith/.hermes/lilith-os-dev"
API_DIR="${APP_ROOT}/api"
LIVE_APP="${API_DIR}/app.py"
VENV_DIR="${APP_ROOT}/api-venv"
SERVICE_NAME="lilith-os-api-dev.service"
HEALTH_URL="http://127.0.0.1:8765/health"

BACKUP=""
if [[ -f "${LIVE_APP}" ]]; then
  BACKUP="${LIVE_APP}.bak.gitdeploy.$(date -u +%Y%m%dT%H%M%SZ)"
fi

rollback() {
  echo "--- DEV ROLLBACK ---"

  if [[ -n "${BACKUP}" && -f "${BACKUP}" ]]; then
    install -o "${APP_USER}" -g "${APP_GROUP}" -m 700 "${BACKUP}" "${LIVE_APP}"
    systemctl restart "${SERVICE_NAME}" || true
    sleep 3
    curl -fsS "${HEALTH_URL}" || true
    echo
  else
    echo "No previous DEV app available for rollback." >&2
    systemctl stop "${SERVICE_NAME}" || true
  fi
}

cleanup() {
  rm -f "${CANDIDATE_APP}" "${CANDIDATE_REQ}" "$0" || true
}

trap cleanup EXIT

echo "--- VERIFY DEV RUNTIME ---"
test -x "${VENV_DIR}/bin/python"
test -d "${API_DIR}"

echo "--- INSTALL DEV PYTHON DEPENDENCIES ---"
"${VENV_DIR}/bin/python" -m pip install   --disable-pip-version-check   -r "${CANDIDATE_REQ}"

echo "--- DEV PYTHON SYNTAX CHECK ---"
runuser -u "${APP_USER}" --   "${VENV_DIR}/bin/python"   -c 'from pathlib import Path; import sys; p=Path(sys.argv[1]); compile(p.read_text(), str(p), "exec"); print("DEV PYTHON SYNTAX: PASS")'   "${CANDIDATE_APP}"

if [[ -f "${LIVE_APP}" ]]; then
  echo "--- BACKUP CURRENT DEV FILE ---"
  cp "${LIVE_APP}" "${BACKUP}"
  chown "${APP_USER}:${APP_GROUP}" "${BACKUP}"
  chmod 700 "${BACKUP}"
  echo "Backup: ${BACKUP}"
fi

echo "--- INSTALL DEV APPLICATION ---"
install -o "${APP_USER}" -g "${APP_GROUP}" -m 700   "${CANDIDATE_APP}"   "${LIVE_APP}"

echo "--- ENABLE DEV SERVICE ---"
systemctl enable "${SERVICE_NAME}"

echo "--- RESTART DEV SERVICE ---"
if ! systemctl restart "${SERVICE_NAME}"; then
  echo "DEV service restart failed." >&2
  rollback
  exit 1
fi

sleep 3

echo "--- DEV SERVICE STATUS ---"
if ! systemctl is-active --quiet "${SERVICE_NAME}"; then
  systemctl status "${SERVICE_NAME}" --no-pager -l || true
  journalctl -u "${SERVICE_NAME}" -n 50 --no-pager || true
  rollback
  exit 1
fi

systemctl is-active "${SERVICE_NAME}"

echo "--- DEV HEALTH CHECK ---"
if ! curl -fsS "${HEALTH_URL}"; then
  echo
  echo "DEV health check failed." >&2
  journalctl -u "${SERVICE_NAME}" -n 50 --no-pager || true
  rollback
  exit 1
fi
echo

echo "--- RECENT DEV LOGS ---"
journalctl -u "${SERVICE_NAME}" -n 20 --no-pager

echo "--- DEV DEPLOYMENT COMPLETE ---"
