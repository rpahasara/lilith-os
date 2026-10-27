#!/usr/bin/env bash
# F8 rollback (root). Touches ONLY F8-owned paths (allowlist in RUNBOOK §4). Never touches lilith-os-api-dev, the
# broker, authority or witness, their files, sockets, credentials, users or groups, and never deletes anything.
#   R-1  rollback.sh stop     stop+disable the gateway and the retention timer (Core API console returns 502 as before F8)
#   R-2  rollback.sh remove   R-1 + MOVE every F8 artefact to /var/backups/hermes-gateway-dev/rollback-<UTC>/ (root 0700)
# F9-C: also stops/disables the erasure executor, hold and reconcile units and moves their unit files, the executor
# config and the tmpfiles entry. It NEVER moves /var/lib/hermes-forget (erasure epochs = restore-guard input, receipts,
# journals, intents), and R-2 refuses while a FORGET is pending (intent or erasure marker present): removing the
# executor then would strand an accepted FORGET. R-1 (stop) is always allowed and keeps every hold in place.
# Works on a partial install (every step is conditional). daemon-reload only runs when nothing else is pending (C-3)
# and the pre-existing services are unchanged across it; otherwise it prints F8_ROLLBACK_HOLD and leaves the reload to
# the owner (the gateway is already stopped and its files moved).
set -Eeuo pipefail
umask 077
MODE=${1:?usage: rollback.sh stop|remove}
HH=/home/lilith/.hermes-dev
SD=/etc/systemd/system
F9C_UNITS="hermes-forget.path hermes-forget-hold.path hermes-forget-reconcile.timer hermes-forget-reconcile.service hermes-forget-restart.service hermes-forget-executor.service hermes-forget-hold.service"
F8_UNITS="${F9C_UNITS} hermes-gateway-dev.service hermes-gateway-dev-retention.timer hermes-gateway-dev-retention.service hermes-provider-gate-dev.service"
EXISTING_UNITS="lilith-os-api-dev.service lilith-memory-broker.service lilith-memory-broker.socket lilith-authority-dev.service lilith-authority-dev.socket lilith-recovery-witness.service lilith-recovery-witness-owner.socket lilith-recovery-witness-signer.socket lilith-stage3-a2-final.service"
service_state() {
  for u in ${EXISTING_UNITS}; do
    printf '%s ' "$u"; systemctl show "$u" -p ActiveState,SubState,MainPID,InvocationID,NRestarts,ExecMainStartTimestampMonotonic | tr '\n' ' '; echo
  done
}
[[ $(id -u) -eq 0 ]] || { echo "not root" >&2; exit 1; }
for u in ${F8_UNITS}; do
  if [[ $(systemctl show "$u" -p LoadState --value 2>/dev/null) == loaded ]]; then
    systemctl stop "$u" || true
    # --no-reload: a plain enable/disable performs an implicit daemon-reload, which would bypass the C-3 guard below.
    if [[ $(systemctl show "$u" -p UnitFileState --value) == enabled ]]; then systemctl disable --no-reload "$u"; fi
  fi
done
! ss -Hltn 'sport = :9901' | grep -q . || { echo "F8_ROLLBACK_FAIL 9901 still listening" >&2; exit 1; }
! ss -Hltn 'sport = :9911' | grep -q . || { echo "F8_ROLLBACK_FAIL 9911 still listening" >&2; exit 1; }
if [[ ${MODE} == stop ]]; then echo "F8_ROLLBACK_STOPPED"; exit 0; fi
[[ ${MODE} == remove ]] || { echo "unknown mode" >&2; exit 2; }
shopt -s nullglob
pending_forget=(/var/lib/hermes-forget/intent/*.intent /var/lib/hermes-forget/in-progress)
shopt -u nullglob
if [[ ${#pending_forget[@]} -gt 0 ]]; then
  echo "F9C_ROLLBACK_REFUSED_FORGET_PENDING: finish or cancel the FORGET first (units stopped, holds kept)" >&2; exit 1
fi

Q=/var/backups/hermes-gateway-dev/rollback-$(date -u +%Y%m%dT%H%M%SZ)
install -d -o root -g root -m 0700 /var/backups/hermes-gateway-dev
install -d -o root -g root -m 0700 "${Q}" "${Q}/etc" "${Q}/hermes-dev" "${Q}/opt"
moved=0
for f in ${SD}/hermes-gateway-dev.service ${SD}/hermes-gateway-dev-retention.service ${SD}/hermes-gateway-dev-retention.timer \
         ${SD}/hermes-gateway-dev.service.d ${SD}/hermes-gateway-dev-retention.service.d \
         ${SD}/hermes-provider-gate-dev.service ${SD}/hermes-provider-gate-dev.service.d \
         /etc/systemd/journald@hermes-gateway-dev.conf /etc/hermes-gateway-dev /etc/hermes-provider-gate-dev \
         ${SD}/hermes-forget-executor.service ${SD}/hermes-forget.path ${SD}/hermes-forget-restart.service \
         ${SD}/hermes-forget-reconcile.service ${SD}/hermes-forget-reconcile.timer ${SD}/hermes-forget-hold.service \
         ${SD}/hermes-forget-hold.path /etc/hermes-forget /etc/tmpfiles.d/hermes-forget.conf; do
  if [[ -e $f || -L $f ]]; then mv "$f" "${Q}/etc/"; moved=1; fi
done
if [[ -d /opt/hermes-gateway-dev ]]; then mv /opt/hermes-gateway-dev "${Q}/opt/"; fi
# F8r3 provider gate state (DynamicUser StateDirectory: /var/lib/private/<name> + /var/lib/<name> symlink).
# The quarantined /etc/hermes-provider-gate-dev holds the Groq key (root 0600): REVOKE the key at Groq, then purge.
install -d -o root -g root -m 0700 "${Q}/var-lib"
for f in /var/lib/hermes-provider-gate-dev /var/lib/private/hermes-provider-gate-dev; do
  if [[ -e $f || -L $f ]]; then mv "$f" "${Q}/var-lib/$(basename "$(dirname "$f")")-$(basename "$f")"; moved=1; fi
done
# HERMES_HOME: everything except the pre-existing memories/ came from F8 or from the gateway at runtime.
shopt -s dotglob nullglob
for p in "${HH}"/*; do [[ $(basename "$p") == memories ]] || mv "$p" "${Q}/hermes-dev/"; done
# Always stop the namespace journald (F8-owned instance) before moving its files, so no stale writer survives the move.
systemctl stop systemd-journald@hermes-gateway-dev.socket systemd-journald-varlink@hermes-gateway-dev.socket   systemd-journald@hermes-gateway-dev.service 2>/dev/null || true
J="/var/log/journal/$(cat /etc/machine-id).hermes-gateway-dev"
if [[ -d ${J} ]]; then mv "${J}" "${Q}/"; fi
chmod -R go-rwx "${Q}"

if [[ ${moved} -eq 1 ]]; then
  # F8-owned units (gateway, retention, provider gate, journal namespace) are expected to be pending after their files
  # moved; only OTHER units' pending changes withhold the reload.
  pending=$(systemctl list-units --all --no-legend --plain | awk '{print $1}'     | grep -v -E '^(hermes-gateway-dev|hermes-provider-gate-dev|hermes-forget|systemd-journald(-varlink)?@hermes-gateway-dev)' \
    | while read -r u; do [[ $(systemctl show "$u" -p NeedDaemonReload --value 2>/dev/null) == yes ]] && echo "$u"; done || true)
  # Transient jobs (timers, tmpfiles, agents) are normal: wait up to 60 s for the queue to drain before holding.
  for _ in $(seq 1 30); do [[ $(systemctl list-jobs --no-legend | wc -l) -eq 0 ]] && break; sleep 2; done
  jobs=$(systemctl list-jobs --no-legend | awk '{print $2"/"$3}' | paste -sd' ')
  if [[ -n ${pending} || -n ${jobs} ]]; then
    echo "F8_ROLLBACK_HOLD daemon-reload withheld: other units pending [${pending//$'\n'/ }] jobs [${jobs}]; owner decides"
  else
    before=$(service_state); systemctl daemon-reload; after=$(service_state)
    [[ "${before}" == "${after}" ]] || { echo "F8_ROLLBACK_FAIL EXISTING_SERVICE_STATE_CHANGED_ACROSS_RELOAD" >&2; exit 1; }
  fi
fi
latest=$(ls -d /var/backups/hermes-gateway-dev/pre-* 2>/dev/null | tail -1 || true)
if [[ -n ${latest} ]]; then
  if find "${HH}" -printf '%M %u:%g %s %P\n' | LC_ALL=C sort -k4 | diff -u "${latest}/hermes-dev-home.listing" -; then
    echo "HERMES_HOME listing == G-1 backup ${latest##*/}"
  else
    echo "F8_ROLLBACK_WARN HERMES_HOME differs from G-1 listing"; exit 1
  fi
fi
echo "F8_ROLLBACK_REMOVED quarantine=${Q}"
