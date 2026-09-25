#!/usr/bin/env bash
# Owner break-glass DEV runtime bootstrap (15B2b-B1c). Never run from routine
# GitHub deployment: the routine deployer has no root and cannot execute it.
set -Eeuo pipefail

APP_USER="lilith"
APP_GROUP="lilith"

HERMES_HOME="/home/lilith/.hermes-dev"
APP_ROOT="/home/lilith/.hermes/lilith-os-dev"
RELEASES_DIR="${APP_ROOT}/releases"
CURRENT_LINK="${APP_ROOT}/current"
VENV_DIR="${APP_ROOT}/api-venv"
DATA_DIR="${APP_ROOT}/data"
DB_PATH="${DATA_DIR}/lilith-dev.db"
COGNITIVE_DB_PATH="${DATA_DIR}/cognitive_memory.dev.db"
PRIVACY_DB_PATH="${DATA_DIR}/privacy_governance.dev.db"
ACTIVATION_DIR="/etc/lilith-os-dev"
CANONICAL_CONFIG_PATH="${ACTIVATION_DIR}/canonical-runtime.json"

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
install -d -o "${APP_USER}" -g "${APP_GROUP}" -m 700 \
  "${HERMES_HOME}" \
  "${HERMES_HOME}/memories" \
  "${APP_ROOT}" \
  "${RELEASES_DIR}" \
  "${DATA_DIR}"

echo "--- CREATE ROOT-OWNED DARK ACTIVATION CONFIG ---"
install -d -o root -g root -m 755 "${ACTIVATION_DIR}"
if [[ ! -e "${CANONICAL_CONFIG_PATH}" ]]; then
  install -o root -g "${APP_GROUP}" -m 640 /dev/null "${CANONICAL_CONFIG_PATH}"
  cat > "${CANONICAL_CONFIG_PATH}" <<'EOF'
{"activeCapabilities":[],"canonicalLtmEnabled":false,"schemaVersion":1}
EOF
fi

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
Environment="LILITH_ENV=dev"
Environment="LILITH_COGNITIVE_DB_PATH=${COGNITIVE_DB_PATH}"
Environment="LILITH_PRIVACY_DB_PATH=${PRIVACY_DB_PATH}"
Environment="LILITH_CANONICAL_CONFIG_FILE=${CANONICAL_CONFIG_PATH}"
WorkingDirectory=${CURRENT_LINK}
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
echo "Current release: ${CURRENT_LINK}"
echo "Releases: ${RELEASES_DIR}"
echo "Venv: ${VENV_DIR}"
echo "Data directory: ${DATA_DIR}"
echo "DB: ${DB_PATH}"
echo "Cognitive DB: ${COGNITIVE_DB_PATH}"
echo "Privacy DB: ${PRIVACY_DB_PATH}"
echo "Canonical config: ${CANONICAL_CONFIG_PATH} (disabled)"
echo "Hermes DEV home: ${HERMES_HOME}"
