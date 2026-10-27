#!/usr/bin/env bash
# F8 DEV Hermes install (lilith-dev-01), F8r3 Phase B (validate profile). Run as root from the extracted, hash-verified package directory:
#   sudo bash bin/install.sh
# Stages files, builds the venv OFFLINE from the bundled wheelhouse, installs the units and reloads systemd ONLY when
# the C-3 preconditions hold and the pre-existing services are proven unchanged across the reload.
# It does NOT create the console token or ANY provider credential (the owner provisions the Groq key at G-5b),
# enable or start anything (gates G-5/G-6 do that).
# No apt, no network, no change to existing units, users, groups, firewall, Core API, broker, authority or witness.
# Any failure exits non-zero with F8_INSTALL_FAIL; recovery is rollback.sh remove (R-2), then G-9.
set -Eeuo pipefail
umask 022
PKG="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REL_ID="$(cat "${PKG}/RELEASE_ID")"
BASE=/opt/hermes-gateway-dev
REL="${BASE}/releases/${REL_ID}"
HH=/home/lilith/.hermes-dev
ETC=/etc/hermes-gateway-dev
SD=/etc/systemd/system
UNIT="${SD}/hermes-gateway-dev.service"
NEW_FILES="${UNIT} ${SD}/hermes-gateway-dev-retention.service ${SD}/hermes-gateway-dev-retention.timer ${SD}/hermes-provider-gate-dev.service /etc/systemd/journald@hermes-gateway-dev.conf"
GATE_ETC=/etc/hermes-provider-gate-dev
PYDIR="${REL}/python/cpython-3.11.16-linux-x86_64-gnu"
RO_STUBS="skills optional-skills optional-mcps hooks scripts bin node node_modules"
EXISTING_UNITS="lilith-os-api-dev.service lilith-memory-broker.service lilith-memory-broker.socket lilith-authority-dev.service lilith-authority-dev.socket lilith-recovery-witness.service lilith-recovery-witness-owner.socket lilith-recovery-witness-signer.socket lilith-stage3-a2-final.service"
die() { echo "F8_INSTALL_FAIL $*" >&2; exit 1; }
step() { echo "--- $*"; }
# Failure-injection hook for the WSL simulation only (F8_SIM=1 is refused on lilith-dev-01 below).
inject() { if [[ ${F8_SIM:-} == 1 && ${F8_FAIL_AT:-} == "$1" ]]; then die "INJECTED_FAILURE at $1"; fi; }
service_state() {
  for u in ${EXISTING_UNITS}; do
    printf '%s ' "$u"; systemctl show "$u" -p ActiveState,SubState,MainPID,InvocationID,NRestarts,ExecMainStartTimestampMonotonic | tr '\n' ' '; echo
  done
}
reload_preconditions() {   # C-3: refuse to reload systemd unless nothing else is pending or in motion
  local pending jobs lockers t next now
  pending=$(systemctl list-units --all --no-legend --plain | awk '{print $1}' \
    | while read -r u; do [[ $(systemctl show "$u" -p NeedDaemonReload --value 2>/dev/null) == yes ]] && echo "$u"; done || true)
  [[ -z ${pending} ]] || die "NEED_DAEMON_RELOAD_PENDING ${pending//$'\n'/ }"
  jobs=$(systemctl list-jobs --no-legend | wc -l); [[ ${jobs} -eq 0 ]] || die "SYSTEMD_JOBS_QUEUED ${jobs}"
  lockers=$(find /proc/[0-9]*/fd -lname '/var/lib/dpkg/lock*' 2>/dev/null | cut -d/ -f3 | sort -u | tr '\n' ' ')
  [[ -z ${lockers} ]] || die "DPKG_LOCK_HELD pids=${lockers}"
  for t in apt-daily.service apt-daily-upgrade.service unattended-upgrades-upgrade.service; do
    [[ $(systemctl show "$t" -p ActiveState --value 2>/dev/null) != activ* ]] || die "APT_ACTIVE $t"
  done
  now=$(date +%s)
  for t in apt-daily.timer apt-daily-upgrade.timer; do
    next=$(systemctl show "$t" -p NextElapseUSecRealtime --value 2>/dev/null)
    [[ -n ${next} && ${next} != n/a ]] || continue
    next=$(date -d "${next}" +%s 2>/dev/null) || continue
    (( next - now > 2700 || next < now )) || die "APT_WINDOW $t fires in $(( (next - now) / 60 )) min"
  done
}

step "preconditions"
[[ $(id -u) -eq 0 ]] || die "not root"
if [[ ${F8_SIM:-} == 1 ]]; then [[ $(hostname) != lilith-dev-01 ]] || die "F8_SIM refused on lilith-dev-01"
else [[ $(hostname) == lilith-dev-01 ]] || die "wrong host $(hostname)"; fi
id lilith >/dev/null 2>&1 || die "user lilith missing"
[[ -d ${HH} && $(stat -c %U:%a "${HH}") == lilith:700 ]] || die "HERMES_HOME missing or not lilith 0700"
[[ ! -e ${REL} && ! -e ${BASE} && ! -e ${ETC} && ! -e ${GATE_ETC} ]] || die "F8 paths already present (rollback first)"
[[ ! -e /var/lib/private/hermes-provider-gate-dev && ! -e /var/lib/hermes-provider-gate-dev ]] || die "gate state already present (rollback first)"
for f in ${NEW_FILES}; do [[ ! -e $f ]] || die "already installed: $f"; done
for p in .env config.yaml lilith_router plugins state.db cron logs cache groq.env auth.json ${RO_STUBS}; do [[ ! -e ${HH}/${p} ]] || die "HERMES_HOME already has ${p}"; done
! ss -Hltn 'sport = :9901' | grep -q . || die "9901 already listening"
! ss -Hltn 'sport = :9911' | grep -q . || die "9911 already listening"
(cd "${PKG}" && sha256sum --quiet -c MANIFEST.sha256) || die "package manifest"
avail_mb=$(df -Pm /opt | awk 'NR==2{print $4}'); (( avail_mb > 2048 )) || die "less than 2 GiB free"
reload_preconditions
inject preconditions

step "stage release ${REL_ID} (root-owned)"
install -d -o root -g root -m 0755 "${BASE}" "${BASE}/releases" "${REL}"
cp -a "${PKG}/src" "${PKG}/python" "${PKG}/bin" "${PKG}/dr5" "${PKG}/RELEASE_ID" "${PKG}/EXPECTED-DISTS.txt" "${REL}/"
chown -R root:root "${REL}"; chmod -R go-w "${REL}"
inject stage

step "venv (offline, hash-checked against uv.lock)"
export UV_NO_CONFIG=1 UV_OFFLINE=1 UV_NO_CACHE=1 UV_PYTHON_DOWNLOADS=never
"${PKG}/uv/uv" venv --python "${PYDIR}/bin/python3.11" --no-project "${REL}/venv"
"${PKG}/uv/uv" pip install --python "${REL}/venv/bin/python" --no-index --find-links "${PKG}/wheelhouse" \
  --require-hashes --no-deps -r "${PKG}/requirements.locked.txt"
"${PKG}/uv/uv" pip install --python "${REL}/venv/bin/python" --no-index --find-links "${PKG}/buildbackend" \
  --no-deps -e "${REL}/src"
"${PKG}/uv/uv" pip list --python "${REL}/venv/bin/python" --format freeze | LC_ALL=C sort > "${REL}/INSTALLED-DISTS.txt"
diff -u "${REL}/EXPECTED-DISTS.txt" "${REL}/INSTALLED-DISTS.txt" || die "installed dists differ from EXPECTED-DISTS"
"${REL}/venv/bin/python" -I -B -c "import hermes_cli.main, gateway.run, yaml" || die "import check"
(cd "${REL}" && find . -name __pycache__ -prune -o -type f ! -name 'RELEASE.sha256*' -print | sed 's|^\./||' \
  | LC_ALL=C sort | xargs -r -d '\n' sha256sum) > "${REL}/RELEASE.sha256.tmp"
mv "${REL}/RELEASE.sha256.tmp" "${REL}/RELEASE.sha256"
chown -R root:root "${REL}"; chmod -R a-w "${REL}"
inject venv

step "HERMES_HOME code + config (root-owned; state stays lilith-owned)"
install -d -o root -g root -m 0755 "${HH}/lilith_router" "${HH}/plugins"
cp -a "${PKG}/home/lilith_router/." "${HH}/lilith_router/"; cp -a "${PKG}/home/plugins/." "${HH}/plugins/"
chown -R root:root "${HH}/lilith_router" "${HH}/plugins"
find "${HH}/lilith_router" "${HH}/plugins" -type d -exec chmod 0755 {} + ; find "${HH}/lilith_router" "${HH}/plugins" -type f -exec chmod 0644 {} +
install -o root -g lilith -m 0640 "${PKG}/home/config.yaml" "${HH}/config.yaml"
install -o root -g lilith -m 0640 "${PKG}/home/router.yaml" "${HH}/lilith_router/router.yaml"
for d in ${RO_STUBS}; do install -d -o root -g root -m 0755 "${HH}/${d}"; done
install -d -o lilith -g lilith -m 0700 "${HH}/logs" "${HH}/cache" "${HH}/cache/xdg" "${HH}/cron"
printf '{"jobs": []}\n' > "${HH}/cron/jobs.json"; chown root:root "${HH}/cron/jobs.json"; chmod 0644 "${HH}/cron/jobs.json"
inject home

step "root-only config dirs (gateway pins; provider gate config + EMPTY root-only credentials dir)"
install -d -o root -g root -m 0750 "${ETC}"
install -d -o root -g root -m 0755 "${GATE_ETC}"
install -d -o root -g root -m 0700 "${GATE_ETC}/credentials"
install -o root -g root -m 0644 "${PKG}/gate/gate.json" "${GATE_ETC}/gate.json"
inject etc

step "unit files (installed; nothing enabled or started)"
install -o root -g root -m 0644 "${PKG}/systemd/journald@hermes-gateway-dev.conf" /etc/systemd/journald@hermes-gateway-dev.conf
install -o root -g root -m 0644 "${PKG}/systemd/hermes-gateway-dev-retention.service" "${SD}/"
install -o root -g root -m 0644 "${PKG}/systemd/hermes-gateway-dev-retention.timer" "${SD}/"
install -o root -g root -m 0644 "${PKG}/systemd/hermes-gateway-dev.service" "${UNIT}"
install -o root -g root -m 0644 "${PKG}/systemd/hermes-provider-gate-dev.service" "${SD}/"
ln -sfn "releases/${REL_ID}" "${BASE}/current.new" && mv -Tf "${BASE}/current.new" "${BASE}/current"
systemd-analyze verify "${UNIT}" "${SD}/hermes-gateway-dev-retention.service" "${SD}/hermes-gateway-dev-retention.timer" "${SD}/hermes-provider-gate-dev.service" 2>&1 \
  | grep -v -e '^$' || true
bash "${REL}/bin/pin_critical.sh" "${REL}"
inject units

step "daemon-reload (C-3 guarded)"
reload_preconditions
before=$(service_state)
inject reload
systemctl daemon-reload
after=$(service_state)
[[ "${before}" == "${after}" ]] || { diff <(echo "${before}") <(echo "${after}"); die "EXISTING_SERVICE_STATE_CHANGED_ACROSS_RELOAD"; }
for u in hermes-gateway-dev hermes-provider-gate-dev; do
  [[ $(for k in LoadState UnitFileState; do systemctl show $u -p $k --value; done | paste -sd' ') == "loaded static" ]] || die "$u not loaded/static"
done
inject verify
"${REL}/venv/bin/python" -I -B "${REL}/bin/verify_release.py" --full || echo "(expected before G-5: console token not yet provisioned)"
echo "F8_INSTALL_STAGED ${REL_ID}"
