#!/usr/bin/env bash
set -Eeuo pipefail

CANDIDATE="${1:?candidate path required}"
LIVE="${2:?live app path required}"
SERVICE="${3:?systemd service required}"
BACKUP="${LIVE}.bak.gitdeploy.$(date -u +%Y%m%dT%H%M%SZ)"
HEALTH_URL="http://127.0.0.1:8765/health"
PYTHON_BIN="/home/lilith/.hermes/lilith-os/api-venv/bin/python"

rollback() {
  echo "--- ROLLBACK ---"
  if [[ -f "${BACKUP}" ]]; then
    install -o lilith -g lilith -m 700 "${BACKUP}" "${LIVE}"
    systemctl restart "${SERVICE}" || true
    sleep 3
    curl -fsS "${HEALTH_URL}" || true
    echo
  else
    echo "Rollback backup not found: ${BACKUP}" >&2
  fi
}

cleanup() {
  rm -f "${CANDIDATE}" "$0" || true
}

trap cleanup EXIT

echo "--- PRODUCTION PYTHON SYNTAX CHECK ---"
runuser -u lilith -- "${PYTHON_BIN}" -c 'from pathlib import Path; import sys; p=Path(sys.argv[1]); compile(p.read_text(), str(p), "exec"); print("PRODUCTION PYTHON SYNTAX: PASS")' "${CANDIDATE}"

echo "--- BACKUP CURRENT LIVE FILE ---"
cp "${LIVE}" "${BACKUP}"
chown lilith:lilith "${BACKUP}"
chmod 700 "${BACKUP}"
echo "Backup: ${BACKUP}"

echo "--- INSTALL NEW FILE ---"
install -o lilith -g lilith -m 700 "${CANDIDATE}" "${LIVE}"

echo "--- RESTART SERVICE ---"
if ! systemctl restart "${SERVICE}"; then
  echo "Service restart failed." >&2
  rollback
  exit 1
fi

sleep 3

echo "--- SERVICE STATUS ---"
if ! systemctl is-active --quiet "${SERVICE}"; then
  systemctl status "${SERVICE}" --no-pager -l || true
  rollback
  exit 1
fi
systemctl is-active "${SERVICE}"

echo "--- HEALTH CHECK ---"
if ! curl -fsS "${HEALTH_URL}"; then
  echo
  echo "Health check failed." >&2
  journalctl -u "${SERVICE}" -n 40 --no-pager || true
  rollback
  exit 1
fi
echo

echo "--- RECENT LOGS ---"
journalctl -u "${SERVICE}" -n 20 --no-pager

echo "--- DEPLOYMENT COMPLETE ---"
