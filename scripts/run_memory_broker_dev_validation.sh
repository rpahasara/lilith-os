#!/usr/bin/env bash
# Trusted transient validation on lilith-dev-01; no broker installation.
set -Eeuo pipefail

test "$#" -eq 6
ARCHIVE="$1"
ATTESTATION="$2"
CANDIDATE_SHA="$3"
VALIDATOR="$4"
SYSTEM_PYTHON="$5"
LIFECYCLE="$6"
WORKSPACE="$(dirname -- "$ARCHIVE")"
[[ "$WORKSPACE" =~ ^/tmp/lilith-broker-validation-[0-9]+-[0-9]+$ ]]
test ! -L "$WORKSPACE"
test "$(stat -c '%a' -- "$WORKSPACE")" = "700"
test "$LIFECYCLE" = "${WORKSPACE}/lifecycle.py"
test -f "$LIFECYCLE" && test ! -L "$LIFECYCLE"
VENV_DIR="${WORKSPACE}/venv"

cleanup() {
  rm -rf -- "$VENV_DIR"
  rm -f -- "$ARCHIVE" "$ATTESTATION" "$VALIDATOR" "$LIFECYCLE" "$0"
  rmdir -- "$WORKSPACE"
}
trap cleanup EXIT

STATE_ROOT="/home/lilith/.hermes/lilith-os-dev/data"

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

BEFORE_LIFECYCLE="$(sudo -n /usr/bin/python3 -B "$LIFECYCLE" snapshot)"
BEFORE_CUSTODY="$(custody_snapshot)"
echo 'BROKER_DEV_TRUSTED_LIFECYCLE_PRECHECK_OK'
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
AFTER_LIFECYCLE="$(sudo -n /usr/bin/python3 -B "$LIFECYCLE" snapshot)"
AFTER_CUSTODY="$(custody_snapshot)"
test "$BEFORE_LIFECYCLE" = "$AFTER_LIFECYCLE"
test "$BEFORE_CUSTODY" = "$AFTER_CUSTODY"
echo 'BROKER_DEV_TRANSIENT_CLEANUP_AND_CUSTODY_OK'
