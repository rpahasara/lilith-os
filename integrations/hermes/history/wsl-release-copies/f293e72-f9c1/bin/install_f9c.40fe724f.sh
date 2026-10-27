#!/usr/bin/env bash
# F9-C DEV install of the Hermes erasure executor + hold-first FORGET (lilith-dev-01, DEV_SYNTHETIC). Run as root from
# the extracted, hash-verified f9c package directory AFTER bin/install.sh staged the release, and BEFORE G-5/G-6:
#   sudo F9C_CORE_API_DIR=<deployed core-api>/lilith_memory F9C_PRIVACY_SECRET=<DEV privacy key file> bash bin/install_f9c.sh
#   sudo F9C_CORE_API_DIR=... F9C_PRIVACY_SECRET=... bash bin/install_f9c.sh --repin   (after a Core API redeploy only)
# Creates the lilith-forget group (Core API identity lilith joins it: takes effect when the Core API restarts), the
# tmpfiles paths, /etc/hermes-forget/executor.json (pins the five Privacy modules of the DEPLOYED Core API; a later
# redeploy makes the executor refuse until --repin), the units and the gateway drop-in; C-3-guarded daemon-reload with
# protected-service parity; enables the two path units and the reconcile timer. Starts nothing else. No sudoers, polkit,
# deployer, Core API, broker, authority or witness change. Failure: F9C_INSTALL_FAIL; recovery is bin/rollback.sh.
set -Eeuo pipefail
umask 022
PKG="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REL_ID="$(cat "${PKG}/RELEASE_ID")"
SD=/etc/systemd/system
CFG=/etc/hermes-forget/executor.json
UNITS="hermes-forget-executor.service hermes-forget.path hermes-forget-restart.service hermes-forget-reconcile.service hermes-forget-reconcile.timer hermes-forget-hold.service hermes-forget-hold.path"
ENABLE="hermes-forget.path hermes-forget-hold.path hermes-forget-reconcile.timer"
MODS="__init__.py canonical_contracts.py memory_action_v2.py canonical_authority.py privacy_governance.py"
EXISTING_UNITS="lilith-os-api-dev.service lilith-memory-broker.service lilith-memory-broker.socket lilith-authority-dev.service lilith-authority-dev.socket lilith-recovery-witness.service lilith-recovery-witness-owner.socket lilith-recovery-witness-signer.socket lilith-stage3-a2-final.service"
PRIVACY_DB=${F9C_PRIVACY_DB:-/home/lilith/.hermes/lilith-os-dev/data/privacy_governance.dev.db}
die() { echo "F9C_INSTALL_FAIL $*" >&2; exit 1; }
step() { echo "--- $*"; }
service_state() {
  for u in ${EXISTING_UNITS}; do
    printf '%s ' "$u"; systemctl show "$u" -p ActiveState,SubState,MainPID,InvocationID,NRestarts,ExecMainStartTimestampMonotonic | tr '\n' ' '; echo
  done
}
reload_preconditions() {   # C-3, as install.sh: refuse while anything else is pending or in motion
  local pending jobs
  pending=$(systemctl list-units --all --no-legend --plain | awk '{print $1}' | grep -v -E '^hermes-forget' \
    | while read -r u; do [[ $(systemctl show "$u" -p NeedDaemonReload --value 2>/dev/null) == yes ]] && echo "$u"; done || true)
  [[ -z ${pending} ]] || die "NEED_DAEMON_RELOAD_PENDING ${pending//$'\n'/ }"
  for _ in $(seq 1 30); do jobs=$(systemctl list-jobs --no-legend | wc -l); [[ ${jobs} -eq 0 ]] && break; sleep 2; done
  [[ ${jobs} -eq 0 ]] || die "SYSTEMD_JOBS_QUEUED"
  [[ -z $(find /proc/[0-9]*/fd -lname '/var/lib/dpkg/lock*' 2>/dev/null) ]] || die "DPKG_LOCK_HELD"
}
pins() {   # <core api package dir> : the executor's pinned module digests as JSON
  python3 -I - "$1" <<'PY'
import hashlib, json, sys
mods = ("__init__.py", "canonical_contracts.py", "memory_action_v2.py", "canonical_authority.py", "privacy_governance.py")
print(json.dumps({m: hashlib.sha256(open(f"{sys.argv[1]}/{m}", "rb").read()).hexdigest() for m in mods}, sort_keys=True))
PY
}

step "preconditions"
[[ $(id -u) -eq 0 ]] || die "not root"
if [[ ${F8_SIM:-} == 1 ]]; then [[ $(hostname) != lilith-dev-01 ]] || die "F8_SIM refused on lilith-dev-01"
else [[ $(hostname) == lilith-dev-01 ]] || die "wrong host $(hostname)"; fi
[[ $(basename "$(readlink -f /opt/hermes-gateway-dev/current)") == "${REL_ID}" ]] || die "current release is not ${REL_ID} (run install.sh first)"
for f in hermes_forget_executor.py hermes_restore_guard.py; do [[ -f /opt/hermes-gateway-dev/current/bin/$f ]] || die "release lacks bin/$f"; done
CORE=${F9C_CORE_API_DIR:?set F9C_CORE_API_DIR to the deployed Core API lilith_memory package directory}
SECRET=${F9C_PRIVACY_SECRET:?set F9C_PRIVACY_SECRET to the DEV Privacy authority key file}
CORE=$(readlink -f "${CORE}")
for m in ${MODS} privacy_forget_intent.py hermes_erasure_spool.py hermes_erasure_owner.py privacy_forget_runner.py; do
  [[ -f ${CORE}/$m && ! -L ${CORE}/$m ]] || die "deployed Core API lacks lilith_memory/$m (deploy the F9-C Core API first)"
done
[[ $(stat -c %U "${CORE}/privacy_governance.py") == root ]] || die "deployed Core API code is not root-owned"
[[ -f ${SECRET} && $(stat -c %U "${SECRET}") == root ]] || die "privacy secret missing or not root-owned"
[[ -f ${PRIVACY_DB} ]] || die "DEV Privacy DB missing: ${PRIVACY_DB}"
grep -q "def identity_forget_completed" "${CORE}/privacy_governance.py" || die "deployed privacy_governance.py lacks identity_forget_completed"
if [[ ${1:-} == --repin ]]; then
  [[ -f ${CFG} ]] || die "nothing to re-pin"
  python3 -I - "${CFG}" "$(pins "${CORE}")" "${CORE}" <<'PY'
import json, os, sys
cfg = json.load(open(sys.argv[1])); cfg["coreApiSha256"] = json.loads(sys.argv[2]); cfg["coreApiDir"] = sys.argv[3]
tmp = sys.argv[1] + ".new"; open(tmp, "w").write(json.dumps(cfg, indent=1, sort_keys=True) + "\n"); os.chmod(tmp, 0o644)
os.replace(tmp, sys.argv[1])
PY
  echo "F9C_REPINNED $(sha256sum < "${CFG}" | cut -c1-16)"; exit 0
fi
for u in ${UNITS}; do [[ ! -e ${SD}/$u ]] || die "already installed: $u"; done
[[ ! -e ${CFG} && ! -e /etc/tmpfiles.d/hermes-forget.conf && ! -e ${SD}/hermes-gateway-dev.service.d/50-forget.conf ]] || die "F9-C config already present"
[[ $(systemctl show hermes-gateway-dev -p ActiveState --value) != active ]] || die "gateway running (install before G-6)"
reload_preconditions

step "group lilith-forget (spool, receipts and intents; the Core API identity only)"
getent group lilith-forget >/dev/null || groupadd --system lilith-forget
id -nG lilith | tr ' ' '\n' | grep -qx lilith-forget || usermod -aG lilith-forget lilith

step "tmpfiles paths"
install -o root -g root -m 0644 "${PKG}/systemd/hermes-forget.tmpfiles.conf" /etc/tmpfiles.d/hermes-forget.conf
systemd-tmpfiles --create /etc/tmpfiles.d/hermes-forget.conf
[[ $(stat -c '%a %U:%G' /var/lib/hermes-forget/intent) == "1730 root:lilith-forget" ]] || die "intent directory"
[[ -z $(ls -A /var/lib/hermes-forget/intent) ]] || die "intent directory not empty"

step "executor config (pins the deployed Core API Privacy modules)"
install -d -o root -g root -m 0755 /etc/hermes-forget
python3 -I - "${CORE}" "$(pins "${CORE}")" "${PRIVACY_DB}" "${SECRET}" "$(getent group lilith-forget | cut -d: -f3)" "$(id -u lilith)" \
  "$(cat /etc/machine-id)" > "${CFG}.new" <<'PY'
import json, sys
core, pins, db, secret, gid, uid, mid = sys.argv[1:8]
print(json.dumps({
  "deploymentEnvironment": "DEV_SYNTHETIC", "hermesHome": "/home/lilith/.hermes-dev", "spoolDir": "/run/hermes-forget/spool",
  "stateDir": "/var/lib/hermes-forget/state", "receiptDir": "/var/lib/hermes-forget/receipts", "receiptGid": int(gid),
  "epochLog": "/var/lib/hermes-forget/epochs/epochs.log", "inProgressMarker": "/var/lib/hermes-forget/in-progress",
  "intentDir": "/var/lib/hermes-forget/intent", "backupRoot": "/var/backups/hermes-gateway-dev",
  "journalNamespace": "hermes-gateway-dev", "journalDir": f"/var/log/journal/{mid}.hermes-gateway-dev",
  "gatewayUnit": "hermes-gateway-dev.service", "gatewayPorts": [9901], "requesterUid": int(uid),
  "privacyDb": db, "privacySecret": secret, "coreApiDir": core, "coreApiSha256": json.loads(pins),
}, indent=1, sort_keys=True))
PY
chmod 0644 "${CFG}.new"; mv -f "${CFG}.new" "${CFG}"

step "units + gateway drop-in (installed; only the path units and the timer are enabled)"
for u in ${UNITS}; do install -o root -g root -m 0644 "${PKG}/systemd/$u" "${SD}/$u"; done
install -d -o root -g root -m 0755 "${SD}/hermes-gateway-dev.service.d"
install -o root -g root -m 0644 "${PKG}/systemd/hermes-gateway-dev.service.d/50-forget.conf" "${SD}/hermes-gateway-dev.service.d/50-forget.conf"
systemd-analyze verify $(for u in ${UNITS}; do echo "${SD}/$u"; done) 2>&1 | grep -v -e '^$' || true

step "daemon-reload (C-3 guarded, protected-service parity)"
reload_preconditions
before=$(service_state); systemctl daemon-reload; after=$(service_state)
[[ "${before}" == "${after}" ]] || { diff <(echo "${before}") <(echo "${after}"); die "EXISTING_SERVICE_STATE_CHANGED_ACROSS_RELOAD"; }
systemctl enable --no-reload ${ENABLE} >/dev/null 2>&1
before=$(service_state); systemctl start ${ENABLE}; after=$(service_state)
[[ "${before}" == "${after}" ]] || die "EXISTING_SERVICE_STATE_CHANGED_ACROSS_START"
for u in ${ENABLE}; do [[ $(systemctl is-active "$u") == active ]] || die "$u not active"; done
[[ $(systemctl show hermes-gateway-dev -p DropInPaths --value) == *50-forget.conf* ]] || die "gateway drop-in not loaded"
echo "F9C_INSTALLED ${REL_ID} config=$(sha256sum < "${CFG}" | cut -c1-16) (restart the Core API so lilith gains lilith-forget)"
