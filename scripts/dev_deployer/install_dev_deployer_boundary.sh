#!/bin/bash
# LILITH 15B2b-B1c owner break-glass installer for the DEV deployer boundary.
#
# Run only by the owner, as root, on lilith-dev-01, through the owner's own
# gcloud/IAP session -- never from GitHub Actions. Usage:
#
#   sudo bash install_dev_deployer_boundary.sh <sa_POSIX_USER> <SOURCE_DIR>
#
# SOURCE_DIR holds lilith-dev-deploy, sudoers-lilith-dev-deployer.in,
# verify_core_api_bundle.py and run_core_api_dev_durability_probe.py from the
# reviewed commit. The installer never enables canonical LTM, never restarts a
# service, and never touches the Memory Broker, owner services, or Stage III.
set -Eeuo pipefail
umask 022
export PATH=/usr/sbin:/usr/bin:/sbin:/bin

DEPLOYER="${1:?deployer POSIX user required}"
SOURCE_DIR="${2:?source directory required}"
[[ "${DEPLOYER}" =~ ^sa_[0-9]{10,30}$ ]] || { echo "invalid deployer user" >&2; exit 2; }
test "$(id -u)" = 0

LIB_DIR="/usr/local/lib/lilith-dev-deploy"
HELPER="/usr/local/sbin/lilith-dev-deploy"
SUDOERS="/etc/sudoers.d/lilith-dev-deployer"
ACTIVATION_DIR="/etc/lilith-os-dev"
ACTIVATION_FILE="${ACTIVATION_DIR}/canonical-runtime.json"
LEGACY_ACTIVATION_FILE="/home/lilith/.hermes/lilith-os-dev/data/canonical-runtime.json"
UNIT="/etc/systemd/system/lilith-os-api-dev.service"
VENV_DIR="/home/lilith/.hermes/lilith-os-dev/api-venv"
DARK='{"activeCapabilities":[],"canonicalLtmEnabled":false,"schemaVersion":1}'

echo "--- REFUSE A PRIVILEGED DEPLOYER ---"
if id -nG "${DEPLOYER}" 2>/dev/null | tr ' ' '\n' | grep -qxE 'google-sudoers|sudo|adm|root'; then
  echo "deployer is a member of an administrative group" >&2
  exit 1
fi

echo "--- INSTALL FIXED HELPER AND PINNED CONTROLS ---"
install -d -o root -g root -m 0755 "${LIB_DIR}"
install -o root -g root -m 0644 "${SOURCE_DIR}/verify_core_api_bundle.py" "${LIB_DIR}/verify_core_api_bundle.py"
install -o root -g root -m 0644 "${SOURCE_DIR}/run_core_api_dev_durability_probe.py" "${LIB_DIR}/run_core_api_dev_durability_probe.py"
install -o root -g root -m 0755 "${SOURCE_DIR}/lilith-dev-deploy" "${HELPER}"
bash -n "${HELPER}"

echo "--- INSTALL EXACT SUDOERS RULE ---"
rendered="$(mktemp)"
trap 'rm -f -- "${rendered}"' EXIT
sed "s/@DEPLOYER@/${DEPLOYER}/g" "${SOURCE_DIR}/sudoers-lilith-dev-deployer.in" > "${rendered}"
visudo -cf "${rendered}"
install -o root -g root -m 0440 "${rendered}" "${SUDOERS}"
visudo -c

echo "--- MOVE ACTIVATION BEYOND DEPLOYABLE REACH ---"
install -d -o root -g root -m 0755 "${ACTIVATION_DIR}"
if [[ ! -e "${ACTIVATION_FILE}" ]]; then
  if [[ -e "${LEGACY_ACTIVATION_FILE}" ]] && \
     ! python3 -c 'import json,sys; sys.exit(json.load(open(sys.argv[1])) != {"schemaVersion":1,"canonicalLtmEnabled":False,"activeCapabilities":[]})' "${LEGACY_ACTIVATION_FILE}"; then
    echo "legacy activation is not dark; refusing to carry it forward" >&2
    exit 1
  fi
  staged="$(mktemp "${ACTIVATION_DIR}/.canonical-runtime.XXXXXX")"
  printf '%s\n' "${DARK}" > "${staged}"
  chown root:lilith "${staged}"
  chmod 0640 "${staged}"
  mv -T -- "${staged}" "${ACTIVATION_FILE}"
fi
test "$(stat -c '%U:%G %a' -- "${ACTIVATION_DIR}")" = "root:root 755"
test "$(stat -c '%U:%G %a' -- "${ACTIVATION_FILE}")" = "root:lilith 640"

echo "--- POINT THE DEV SERVICE AT ROOT-OWNED ACTIVATION ---"
if ! grep -qxF "Environment=\"LILITH_CANONICAL_CONFIG_FILE=${ACTIVATION_FILE}\"" "${UNIT}"; then
  grep -qxF "Environment=\"LILITH_CANONICAL_CONFIG_FILE=${LEGACY_ACTIVATION_FILE}\"" "${UNIT}"
  sed -i "s#^Environment=\"LILITH_CANONICAL_CONFIG_FILE=${LEGACY_ACTIVATION_FILE}\"\$#Environment=\"LILITH_CANONICAL_CONFIG_FILE=${ACTIVATION_FILE}\"#" "${UNIT}"
fi
test "$(grep -c '^Environment="LILITH_CANONICAL_CONFIG_FILE=' "${UNIT}")" = 1
grep -qxF "Environment=\"LILITH_CANONICAL_CONFIG_FILE=${ACTIVATION_FILE}\"" "${UNIT}"
systemctl daemon-reload
rm -f -- "${LEGACY_ACTIVATION_FILE}"

echo "--- RETURN THE APPLICATION VENV TO THE APPLICATION USER ---"
chown -R lilith:lilith "${VENV_DIR}"

echo "--- INSTALLED BOUNDARY ---"
stat -c '%A %U:%G %n' "${HELPER}" "${LIB_DIR}" "${LIB_DIR}"/* "${SUDOERS}" "${ACTIVATION_DIR}" "${ACTIVATION_FILE}"
sha256sum "${HELPER}" "${LIB_DIR}"/* "${SUDOERS}"
sudo -n -l -U "${DEPLOYER}"
echo "Service restart deferred to the next helper deployment."
