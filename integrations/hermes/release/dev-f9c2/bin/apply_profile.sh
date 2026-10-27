#!/usr/bin/env bash
# F8r3 B-5: switch the installed gateway to the OPERATE profile (after synthetic validation is accepted). Root:
#   sudo bash bin/apply_profile.sh operate
# Changes ONLY F8-owned files: HERMES_HOME/config.yaml (WARNING logging, 24 h history, 60 min idle reset), the
# gateway journal-namespace retention (2 days), a retention drop-in (prune 1 day, logs 2 days); re-pins the critical
# set; reloads systemd only under the C-3 guard with protected-service parity; restarts the gateway only.
set -Eeuo pipefail
PKG="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
[[ ${1:-} == operate ]] || { echo "usage: apply_profile.sh operate" >&2; exit 2; }
[[ $(id -u) -eq 0 ]] || { echo "not root" >&2; exit 1; }
if [[ ${F8_SIM:-} == 1 ]]; then [[ $(hostname) != lilith-dev-01 ]] || exit 1; else [[ $(hostname) == lilith-dev-01 ]] || { echo "wrong host" >&2; exit 1; }; fi
HH=/home/lilith/.hermes-dev; SD=/etc/systemd/system; P=${PKG}/profiles/operate
die() { echo "F8_PROFILE_FAIL $*" >&2; exit 1; }
EXISTING_UNITS="lilith-os-api-dev.service lilith-memory-broker.service lilith-memory-broker.socket lilith-authority-dev.service lilith-authority-dev.socket lilith-recovery-witness.service lilith-recovery-witness-owner.socket lilith-recovery-witness-signer.socket lilith-stage3-a2-final.service"
state() { for u in ${EXISTING_UNITS}; do printf '%s ' "$u"; for k in ActiveState SubState MainPID InvocationID NRestarts; do printf '%s ' "$(systemctl show "$u" -p $k --value)"; done; echo; done; }
pending() { systemctl list-units --all --no-legend --plain | awk '{print $1}' | grep -v '^hermes-' \
  | while read -r u; do [[ $(systemctl show "$u" -p NeedDaemonReload --value 2>/dev/null) == yes ]] && echo "$u"; done || true; }
[[ -z $(pending) && $(systemctl list-jobs --no-legend | wc -l) -eq 0 ]] || die "C-3: other units pending reload / jobs queued"
(cd "${PKG}" && sha256sum --quiet -c MANIFEST.sha256) || die "package manifest"
before=$(state)
systemctl stop hermes-gateway-dev
install -o root -g lilith -m 0640 "${P}/config.yaml" "${HH}/config.yaml"
install -o root -g root -m 0644 "${P}/journald@hermes-gateway-dev.conf" /etc/systemd/journald@hermes-gateway-dev.conf
install -d -o root -g root -m 0755 "${SD}/hermes-gateway-dev-retention.service.d"
install -o root -g root -m 0644 "${P}/10-operate.conf" "${SD}/hermes-gateway-dev-retention.service.d/10-operate.conf"
bash /opt/hermes-gateway-dev/current/bin/pin_critical.sh
[[ -z $(pending) ]] || die "C-3: other units pending reload"
systemctl daemon-reload
systemctl restart systemd-journald@hermes-gateway-dev.service 2>/dev/null || true
systemctl start hermes-gateway-dev
after=$(state)
[[ "${before}" == "${after}" ]] || { diff <(echo "${before}") <(echo "${after}"); die "PROTECTED_SERVICE_STATE_CHANGED"; }
/opt/hermes-gateway-dev/current/venv/bin/python -I -B /opt/hermes-gateway-dev/current/bin/verify_release.py --pre-start
echo "F8_PROFILE_OPERATE_APPLIED level=$(grep -m1 '  level:' ${HH}/config.yaml | awk '{print $2}')"
