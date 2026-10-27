#!/usr/bin/env bash
# F8 rollback (root). Never touches lilith-os-api-dev, the broker, authority, witness, their files, users or groups.
#   R-1  bash rollback.sh stop        stop the gateway (the Core API console returns 502, exactly as before F8)
#   R-2  bash rollback.sh remove      R-1 + remove every F8 artefact. Nothing is deleted: F8 files, including any
#                                     DEV conversation state Hermes wrote, move to a root-only quarantine directory
#                                     /var/backups/hermes-gateway-dev/rollback-<UTC>/ for owner review or purge.
# After R-2 the HERMES_HOME listing must equal the G-1 backup listing (checked below).
set -Eeuo pipefail
umask 077
MODE=${1:?usage: rollback.sh stop|remove}
HH=/home/lilith/.hermes-dev
[[ $(id -u) -eq 0 ]] || { echo "not root" >&2; exit 1; }
for u in hermes-gateway-dev-retention.timer hermes-gateway-dev.service; do
  systemctl stop "$u" 2>/dev/null || true; systemctl disable "$u" 2>/dev/null || true
done
! ss -Hltn 'sport = :9901' | grep -q . || { echo "F8_ROLLBACK_FAIL 9901 still listening" >&2; exit 1; }
[[ ${MODE} == stop ]] && { echo "F8_ROLLBACK_STOPPED"; exit 0; }
[[ ${MODE} == remove ]] || { echo "unknown mode" >&2; exit 2; }

Q=/var/backups/hermes-gateway-dev/rollback-$(date -u +%Y%m%dT%H%M%SZ)
install -d -o root -g root -m 0700 "${Q}" "${Q}/etc" "${Q}/hermes-dev" "${Q}/opt"
for f in /etc/systemd/system/hermes-gateway-dev.service /etc/systemd/system/hermes-gateway-dev-retention.service \
         /etc/systemd/system/hermes-gateway-dev-retention.timer /etc/systemd/journald@hermes-gateway-dev.conf; do
  [[ -e $f ]] && mv "$f" "${Q}/etc/"
done
[[ -d /etc/systemd/system/hermes-gateway-dev.service.d ]] && mv /etc/systemd/system/hermes-gateway-dev.service.d "${Q}/etc/"
[[ -d /etc/hermes-gateway-dev ]] && mv /etc/hermes-gateway-dev "${Q}/etc/"
systemctl daemon-reload
systemctl stop systemd-journald@hermes-gateway-dev.service 2>/dev/null || true
[[ -d /var/log/journal/$(cat /etc/machine-id).hermes-gateway-dev ]] && mv "/var/log/journal/$(cat /etc/machine-id).hermes-gateway-dev" "${Q}/"
# Everything in HERMES_HOME except the pre-existing memories/ directory came from F8 or from the gateway at runtime.
shopt -s dotglob nullglob
for p in "${HH}"/*; do [[ $(basename "$p") == memories ]] || mv "$p" "${Q}/hermes-dev/"; done
[[ -d /opt/hermes-gateway-dev ]] && mv /opt/hermes-gateway-dev "${Q}/opt/"
chmod -R go-rwx "${Q}"
latest=$(ls -d /var/backups/hermes-gateway-dev/pre-* 2>/dev/null | tail -1)
if [[ -n ${latest} ]]; then
  find "${HH}" -printf '%M %u:%g %s %P\n' | LC_ALL=C sort -k4 | diff -u "${latest}/hermes-dev-home.listing" - \
    && echo "HERMES_HOME listing == G-1 backup" || echo "F8_ROLLBACK_WARN HERMES_HOME differs from G-1 listing (memories/ content changed?)"
fi
echo "F8_ROLLBACK_REMOVED quarantine=${Q}"
