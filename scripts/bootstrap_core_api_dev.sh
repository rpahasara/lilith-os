#!/usr/bin/env bash
set -Eeuo pipefail

APP_USER="lilith"
APP_GROUP="lilith"

HERMES_HOME="/home/lilith/.hermes-dev"
APP_ROOT="/home/lilith/.hermes/lilith-os-dev"
API_DIR="${APP_ROOT}/api"
VENV_DIR="${APP_ROOT}/api-venv"
DATA_DIR="${APP_ROOT}/data"
DB_PATH="${DATA_DIR}/lilith-dev.db"

SERVICE_NAME="lilith-os-api-dev.service"
SERVICE_PATH="/etc/systemd/system/${SERVICE_NAME}"

echo "--- CREATE APPLICATION USER ---"
if ! id "${APP_USER}" >/dev/null 2>&1; then
  useradd --create-home --shell /bin/bash "${APP_USER}"
fi

echo "--- INSTALL SYSTEM DEPENDENCIES ---"
export DEBIAN_FRONTEND=noninteractive
apt-get update
apt-get install -y python3 python3-venv python3-pip curl

echo "--- CREATE ISOLATED DEV DIRECTORIES ---"
install -d -o "${APP_USER}" -g "${APP_GROUP}" -m 700   "${HERMES_HOME}"   "${HERMES_HOME}/memories"   "${APP_ROOT}"   "${API_DIR}"   "${DATA_DIR}"

echo "--- CREATE PYTHON VENV ---"
if [[ ! -x "${VENV_DIR}/bin/python" ]]; then
  python3 -m venv "${VENV_DIR}"
fi

chown -R "${APP_USER}:${APP_GROUP}" "${VENV_DIR}"

echo "--- WRITE DEV SYSTEMD SERVICE ---"
cat > "${SERVICE_PATH}" <<EOF
[Unit]
Description=LILITH OS Core API DEV
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=${APP_USER}
Group=${APP_GROUP}
Environment="HOME=/home/lilith"
Environment="LILITH_HOME=/home/lilith"
Environment="HERMES_HOME=${HERMES_HOME}"
Environment="LILITH_DATA_DIR=${DATA_DIR}"
Environment="LILITH_DB_PATH=${DB_PATH}"
WorkingDirectory=${API_DIR}
ExecStart=${VENV_DIR}/bin/uvicorn app:app --host 0.0.0.0 --port 8765
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

chmod 644 "${SERVICE_PATH}"

echo "--- RELOAD SYSTEMD ---"
systemctl daemon-reload

echo "--- BOOTSTRAP COMPLETE ---"
echo "Service: ${SERVICE_NAME}"
echo "API directory: ${API_DIR}"
echo "Venv: ${VENV_DIR}"
echo "Data directory: ${DATA_DIR}"
echo "DB: ${DB_PATH}"
echo "Hermes DEV home: ${HERMES_HOME}"
