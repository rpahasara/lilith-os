#!/usr/bin/env bash
# F8 DEV Hermes install (lilith-dev-01). Run as root from the extracted, hash-verified package directory:
#   sudo bash bin/install.sh
# Stages files, builds the venv OFFLINE from the bundled wheelhouse, installs the unit and reloads systemd.
# It does NOT create the console token, provider credential, enable or start anything (gates G-5/G-6 do that).
# No apt, no network, no change to existing units, users, groups, firewall or Core API files.
set -Eeuo pipefail
umask 022
PKG="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REL_ID="$(cat "${PKG}/RELEASE_ID")"
BASE=/opt/hermes-gateway-dev
REL="${BASE}/releases/${REL_ID}"
HH=/home/lilith/.hermes-dev
ETC=/etc/hermes-gateway-dev
UNIT=/etc/systemd/system/hermes-gateway-dev.service
PYDIR="${REL}/python/cpython-3.11.16-linux-x86_64-gnu"
RO_STUBS="skills optional-skills optional-mcps hooks scripts bin node node_modules"
die() { echo "F8_INSTALL_FAIL $*" >&2; exit 1; }
step() { echo "--- $*"; }

step "preconditions"
[[ $(id -u) -eq 0 ]] || die "not root"
[[ $(hostname) == lilith-dev-01 || ${F8_SIM:-} == 1 ]] || die "wrong host $(hostname)"
id lilith >/dev/null 2>&1 || die "user lilith missing"
[[ -d ${HH} && $(stat -c %U:%a "${HH}") == lilith:700 ]] || die "HERMES_HOME missing or not lilith 0700"
[[ ! -e ${REL} ]] || die "release ${REL_ID} already present"
[[ ! -e ${UNIT} ]] || die "unit already installed"
for p in .env config.yaml lilith_router plugins state.db cron ${RO_STUBS}; do [[ ! -e ${HH}/${p} ]] || die "HERMES_HOME already has ${p}"; done
! ss -Hltn 'sport = :9901' | grep -q . || die "9901 already listening"
(cd "${PKG}" && sha256sum --quiet -c MANIFEST.sha256) || die "package manifest"
avail_mb=$(df -Pm /opt | awk 'NR==2{print $4}'); (( avail_mb > 2048 )) || die "less than 2 GiB free"

step "stage release ${REL_ID} (root-owned)"
install -d -o root -g root -m 0755 "${BASE}" "${BASE}/releases"
install -d -o root -g root -m 0755 "${REL}"
trap 'echo "install failed: removing partial ${REL}" >&2; rm -rf --one-file-system "${REL}"' ERR
cp -a "${PKG}/src" "${PKG}/python" "${PKG}/bin" "${PKG}/RELEASE_ID" "${PKG}/EXPECTED-DISTS.txt" "${REL}/"
chown -R root:root "${REL}"
chmod -R go-w "${REL}"

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
trap - ERR

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

step "root-only config dir + critical-set pin"
install -d -o root -g root -m 0750 "${ETC}"
{ for f in gateway/run.py agent/background_review.py tools/memory_tool.py tools/skill_manager_tool.py \
           tools/write_approval.py tools/legacy_canonical_containment.py; do echo "${REL}/src/${f}"; done
  echo "${REL}/bin/verify_release.py"; echo "${HH}/config.yaml"
  find "${HH}/lilith_router" "${HH}/plugins" -type f ! -path '*/__pycache__/*' | LC_ALL=C sort
} | sed 's|^/||' | (cd / && xargs -r sha256sum) > "${ETC}/critical.sha256"
chmod 0600 "${ETC}/critical.sha256"

step "units (installed + daemon-reload; nothing enabled or started)"
for u in hermes-gateway-dev-retention.service hermes-gateway-dev-retention.timer; do
  [[ ! -e /etc/systemd/system/${u} ]] || die "${u} already installed"; done
[[ ! -e /etc/systemd/journald@hermes-gateway-dev.conf ]] || die "journald namespace conf exists"
install -o root -g root -m 0644 "${PKG}/systemd/journald@hermes-gateway-dev.conf" /etc/systemd/journald@hermes-gateway-dev.conf
install -o root -g root -m 0644 "${PKG}/systemd/hermes-gateway-dev-retention.service" /etc/systemd/system/
install -o root -g root -m 0644 "${PKG}/systemd/hermes-gateway-dev-retention.timer" /etc/systemd/system/
install -o root -g root -m 0644 "${PKG}/systemd/hermes-gateway-dev.service" "${UNIT}"
ln -sfn "releases/${REL_ID}" "${BASE}/current.new" && mv -Tf "${BASE}/current.new" "${BASE}/current"
systemd-analyze verify "${UNIT}" 2>&1 | grep -v -e 'Unknown key' || true
systemctl daemon-reload
"${REL}/venv/bin/python" -I -B "${REL}/bin/verify_release.py" --full || echo "(expected before G-5: console token not yet provisioned)"
echo "F8_INSTALL_STAGED ${REL_ID}"
