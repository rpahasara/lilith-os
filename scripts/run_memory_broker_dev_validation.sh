#!/usr/bin/env bash
# Trusted transient validation on lilith-dev-01; no broker installation.
set -Eeuo pipefail

test "$#" -eq 5
ARCHIVE="$1"
ATTESTATION="$2"
CANDIDATE_SHA="$3"
VALIDATOR="$4"
PYTHON="$5"
WORKSPACE="$(dirname -- "$ARCHIVE")"
[[ "$WORKSPACE" =~ ^/tmp/lilith-broker-validation-[0-9]+-[0-9]+$ ]]
test ! -L "$WORKSPACE"
test "$(stat -c '%a' -- "$WORKSPACE")" = "700"

cleanup() {
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
  test ! -e "${STATE_ROOT}/owner_control.db"
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
test -x "$PYTHON"
"$PYTHON" -B "$VALIDATOR" verify-run \
  --archive "$ARCHIVE" \
  --attestation "$ATTESTATION" \
  --candidate-sha "$CANDIDATE_SHA" \
  --python "$PYTHON"
broker_absent
AFTER="$(custody_snapshot)"
test "$BEFORE" = "$AFTER"
echo 'BROKER_DEV_TRANSIENT_CLEANUP_AND_CUSTODY_OK'
