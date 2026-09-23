#!/usr/bin/env bash
# Trusted transient validation on lilith-dev-01; no broker installation.
set -Eeuo pipefail

test "$#" -eq 5
ARCHIVE="$1"
ATTESTATION="$2"
CANDIDATE_SHA="$3"
VALIDATOR="$4"
SYSTEM_PYTHON="$5"
WORKSPACE="$(dirname -- "$ARCHIVE")"
[[ "$WORKSPACE" =~ ^/tmp/lilith-broker-validation-[0-9]+-[0-9]+$ ]]
test ! -L "$WORKSPACE"
test "$(stat -c '%a' -- "$WORKSPACE")" = "700"
VENV_DIR="${WORKSPACE}/venv"

cleanup() {
  rm -rf -- "$VENV_DIR"
  rm -f -- "$ARCHIVE" "$ATTESTATION" "$VALIDATOR" "$0"
  rmdir -- "$WORKSPACE"
}
trap cleanup EXIT

STATE_ROOT="/home/lilith/.hermes/lilith-os-dev/data"
broker_absent() {
  ! getent passwd lilith-memory-broker >/dev/null
  ! getent group lilith-memory-broker >/dev/null
  test "$(systemctl show -p LoadState --value lilith-memory-broker.service)" = "not-found"
  test "$(systemctl show -p LoadState --value lilith-memory-broker.socket)" = "not-found"
  test ! -e /run/lilith-memory
  test ! -e /var/lib/lilith-memory-broker
  sudo test ! -e "${STATE_ROOT}/owner_control.db"
}

custody_snapshot() {
  for path in \
    "${STATE_ROOT}" \
    "${STATE_ROOT}/cognitive_memory.dev.db" \
    "${STATE_ROOT}/privacy_governance.dev.db"; do
    if test -e "$path"; then
      sudo stat -c '%n:%u:%g:%a' -- "$path"
    else
      printf '%s:ABSENT\n' "$path"
    fi
  done
}

broker_absent
BEFORE="$(custody_snapshot)"
echo 'BROKER_DEV_STATE_PRECHECK_OK'
test -x "$SYSTEM_PYTHON"
"$SYSTEM_PYTHON" -m venv "$VENV_DIR"
VENV_PYTHON="${VENV_DIR}/bin/python"
echo 'BROKER_TEST_VENV_READY'
"$VENV_PYTHON" -m pip install --no-input --no-cache-dir --disable-pip-version-check \
  'fido2==2.2.1' 'rfc8785==0.1.4'
echo 'BROKER_TEST_DEPENDENCIES_READY'
"$SYSTEM_PYTHON" -B "$VALIDATOR" verify-run \
  --archive "$ARCHIVE" \
  --attestation "$ATTESTATION" \
  --candidate-sha "$CANDIDATE_SHA" \
  --python "$VENV_PYTHON"
broker_absent
AFTER="$(custody_snapshot)"
test "$BEFORE" = "$AFTER"
echo 'BROKER_DEV_TRANSIENT_CLEANUP_AND_CUSTODY_OK'
