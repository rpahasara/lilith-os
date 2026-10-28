#!/usr/bin/env bash
# Offline simulation of bin/install_cog1.sh on an f9c2-shaped host built from this repository. TEST_ONLY.
# Run as root on a disposable Linux machine; it re-executes itself in a private mount namespace with overlay
# filesystems on /etc /var /opt /home, so nothing outside a scratch directory is written:
#   sudo bash sim_install_cog1.sh <repo-root>
# Uses the real pin_critical.sh and both real release verifiers (rendered with a synthetic token), a systemctl shim
# that reports the gateway state, and F8_SIM=1 (refused on lilith-dev-01). Prints PASS/FAIL per case; exit 0 = all pass.
set -Eeuo pipefail
REPO=$(readlink -f "${1:?repo root}")
if [[ -z ${COG1_SIM_INNER:-} ]]; then
  [[ $(id -u) -eq 0 ]] || { echo "run as root"; exit 2; }
  [[ $(hostname) != lilith-dev-01 ]] || { echo "refused on lilith-dev-01"; exit 2; }
  exec env COG1_SIM_INNER=1 unshare -m --propagation private bash "$0" "$REPO"
fi
S=$(mktemp -d /tmp/cog1sim.XXXXXX)
for d in etc var opt home; do
  mkdir -p "$S/ov/$d/u" "$S/ov/$d/w"
  mount -t overlay overlay -o "lowerdir=/$d,upperdir=$S/ov/$d/u,workdir=$S/ov/$d/w" "/$d"
done
REL9=${REPO}/integrations/hermes/release/dev-f9c2
COG=${REPO}/integrations/hermes/release/dev-f9c2-cog1
INSTALL=${COG}/bin/install_cog1.sh
TOKEN="TEST_ONLY-$(printf 'd0%.0s' $(seq 1 20))"
BASE=/opt/hermes-gateway-dev; OLD=${BASE}/releases/f293e72-f9c2; NEW=${BASE}/releases/f293e72-f9c2-cog1
HH=/home/lilith/.hermes-dev; LR=${HH}/lilith_router
FAILS=0
pass() { echo "PASS $*"; }
fail() { echo "FAIL $*"; FAILS=$((FAILS + 1)); }
check() { if eval "$2"; then pass "$1"; else fail "$1"; fi; }
render() { python3 -I -c 'import sys; sys.stdout.buffer.write(open(sys.argv[1],"rb").read().replace(b"__LILITH_GATE_CLIENT_TOKEN__", sys.argv[2].encode()))' "$1" "$TOKEN"; }

# --- systemctl shim: only the gateway ActiveState query the installer makes -------------------------------------
mkdir -p "$S/bin"
cat > "$S/bin/systemctl" <<'SH'
#!/bin/sh
if [ "$1 $2 $3 $4" = "show hermes-gateway-dev -p ActiveState" ]; then echo "${SIM_GATEWAY_STATE:-inactive}"; exit 0; fi
echo "sim systemctl refused: $*" >&2; exit 1
SH
chmod 0755 "$S/bin/systemctl"; export PATH="$S/bin:$PATH" F8_SIM=1

# --- f9c2-shaped host --------------------------------------------------------------------------------------------
id lilith >/dev/null 2>&1 || useradd --system --no-create-home lilith
install -d -m 0755 "${BASE}" "${BASE}/releases" "${OLD}" "${OLD}/bin" "${OLD}/venv/bin"
cp -a "${REL9}/bin/." "${OLD}/bin/"
render "${REL9}/templates/bin/verify_release.py.tmpl" > "${OLD}/bin/verify_release.py"
for f in gateway/run.py agent/background_review.py tools/memory_tool.py tools/skill_manager_tool.py \
         tools/write_approval.py tools/legacy_canonical_containment.py; do
  install -d "${OLD}/src/$(dirname "$f")"; echo "TEST_ONLY src $f" > "${OLD}/src/$f"
done
ln -s /usr/bin/python3 "${OLD}/venv/bin/python"
printf 'f293e72-f9c2\n' > "${OLD}/RELEASE_ID"
(cd "${OLD}" && find . -name __pycache__ -prune -o -type f ! -name 'RELEASE.sha256*' -print | sed 's|^\./||' \
  | LC_ALL=C sort | xargs -r -d '\n' sha256sum) > "${OLD}/RELEASE.sha256"
chown -R root:root "${OLD}"; chmod -R go-w "${OLD}"; chmod -R a-w "${OLD}"
ln -sfn releases/f293e72-f9c2 "${BASE}/current"

rm -rf "${HH}"; install -d -o lilith -g lilith -m 0700 "${HH}"
python3 -I "${REPO}/integrations/hermes/home/tools/assemble_home.py" --variant dev-f9c2 --out "$S/home" >/dev/null
install -d -o root -g root -m 0755 "${LR}" "${HH}/plugins"
cp -a "$S/home/lilith_router/." "${LR}/"; cp -a "$S/home/plugins/." "${HH}/plugins/"
chown -R root:root "${LR}" "${HH}/plugins"
find "${LR}" "${HH}/plugins" -type d -exec chmod 0755 {} +; find "${LR}" "${HH}/plugins" -type f -exec chmod 0644 {} +
install -o root -g lilith -m 0640 "$S/home/router.yaml" "${LR}/router.yaml"
render "${REL9}/templates/home/config.yaml.tmpl" > "$S/config.yaml"
install -o root -g lilith -m 0640 "$S/config.yaml" "${HH}/config.yaml"
printf 'LILITH_OS_PORT=9901\nLILITH_OS_TOKEN=%s\n' "$(printf 'ab%.0s' $(seq 1 32))" > "$S/env"
install -o root -g lilith -m 0640 "$S/env" "${HH}/.env"
for d in skills optional-skills optional-mcps hooks scripts bin node node_modules; do install -d -o root -g root -m 0755 "${HH}/$d"; done
install -d -o lilith -g lilith -m 0700 "${HH}/logs" "${HH}/cron"
printf '{"jobs": []}\n' > "${HH}/cron/jobs.json"; chown root:root "${HH}/cron/jobs.json"; chmod 0644 "${HH}/cron/jobs.json"
install -d -o root -g root -m 0750 /etc/hermes-gateway-dev
install -d -o root -g root -m 0755 /etc/hermes-provider-gate-dev
install -d -o root -g root -m 0700 /etc/hermes-provider-gate-dev/credentials
render "${REL9}/templates/gate/gate.json.tmpl" > /etc/hermes-provider-gate-dev/gate.json
SD=/etc/systemd/system; install -d "${SD}/hermes-gateway-dev.service.d"
for u in hermes-gateway-dev.service hermes-gateway-dev-retention.service hermes-gateway-dev-retention.timer \
         hermes-provider-gate-dev.service; do install -m 0644 "${REL9}/systemd/$u" "${SD}/$u"; done
install -m 0644 "${REL9}/systemd/hermes-gateway-dev.service.d/50-forget.conf" "${SD}/hermes-gateway-dev.service.d/"
install -m 0644 "${REL9}/systemd/journald@hermes-gateway-dev.conf" /etc/systemd/journald@hermes-gateway-dev.conf
install -d -m 1770 /var/lib/hermes-forget/intent
bash "${OLD}/bin/pin_critical.sh" "${OLD}" >/dev/null

verify() { "${BASE}/current/venv/bin/python" -I -B "${BASE}/current/bin/verify_release.py" --full 2>&1 | tail -1; }
state() {   # every file and link of the release root, HERMES_HOME and the gateway pins (excluding cog1 staging)
  find "${BASE}" "${HH}" /etc/hermes-gateway-dev -path "${NEW}" -prune -o \( -type f -o -type l \) -print \
    | LC_ALL=C sort | while read -r p; do
      if [[ -L $p ]]; then echo "L $p -> $(readlink "$p")"; else echo "F $p $(stat -c %a:%U "$p") $(sha256sum < "$p" | cut -c1-16)"; fi
    done | sha256sum | cut -c1-16
}
payload() {   # $1 = dir: the six reviewed payload files, root 0700
  install -d -o root -g root -m 0700 "$1"
  cp "${REPO}/integrations/hermes/overlays/dev-unified-cognition/lilith_router/world_context.py" "$1/world_context.py"
  cp "${REPO}/integrations/hermes/home/variants/prod-lilith-01/lilith_router/world_context.py" "$1/_prod_world_context.py"
  cp "${REPO}/integrations/hermes/home/variants/dev-f9c2/lilith_router/world_context.py" "$1/world_context.f9c2-stub.py"
  cp "${COG}/templates/bin/verify_release.py.tmpl" "$1/verify_release.cog1.py.tmpl"
  cp "${REL9}/templates/bin/verify_release.py.tmpl" "$1/verify_release.f9c2.py.tmpl"
  cp "${COG}/RELEASE_ID" "$1/RELEASE_ID"
}
run() { set +e; OUT=$("$@" 2>&1); RC=$?; set -e; }

check "baseline f9c2 verify --full" '[[ $(verify) == "F8_VERIFY_PASS full f293e72-f9c2" ]]'
BASELINE=$(state)
OLD_TREE=$(cd "${OLD}" && sha256sum -c --quiet RELEASE.sha256 && find . -type f -o -type l | LC_ALL=C sort | xargs -d '\n' sha256sum 2>/dev/null | sha256sum | cut -c1-16)
P=$S/payload; payload "$P"

# --- refusals before any change -------------------------------------------------------------------------------
payload "$S/p1"; echo "# TEST_ONLY" >> "$S/p1/world_context.py"
run bash "${INSTALL}" install "$S/p1"; check "refuses a changed payload file" '[[ $RC -ne 0 && $OUT == *"payload digest world_context.py"* && $(state) == "$BASELINE" ]]'
payload "$S/p2"; touch "$S/p2/extra"
run bash "${INSTALL}" install "$S/p2"; check "refuses an extra payload file" '[[ $RC -ne 0 && $OUT == *"exactly the payload files"* && $(state) == "$BASELINE" ]]'
payload "$S/p3"; chmod 0755 "$S/p3"
run bash "${INSTALL}" install "$S/p3"; check "refuses a non-0700 payload dir" '[[ $RC -ne 0 && $OUT == *"root 0700"* && $(state) == "$BASELINE" ]]'
touch /var/lib/hermes-forget/intent/test.intent
run bash "${INSTALL}" install "$P"; check "refuses while a FORGET is pending" '[[ $RC -ne 0 && $OUT == *"FORGET pending"* && $(state) == "$BASELINE" ]]'
rm /var/lib/hermes-forget/intent/test.intent
run env SIM_GATEWAY_STATE=active bash "${INSTALL}" install "$P"; check "refuses while the gateway runs" '[[ $RC -ne 0 && $OUT == *"gateway running"* && $(state) == "$BASELINE" ]]'
run bash "${INSTALL}" revert "$P"; check "revert refuses while current is f9c2" '[[ $RC -ne 0 && $OUT == *"current is not f293e72-f9c2-cog1"* && $(state) == "$BASELINE" ]]'

# --- a failure after the first change reverts automatically -------------------------------------------------------
run env F8_FAIL_AT=after_switch bash "${INSTALL}" install "$P"
check "injected failure after switch reverts" '[[ $RC -ne 0 && $OUT == *"INJECTED_FAILURE at after_switch"* && $OUT == *COG1_REVERTED* ]]'
check "  state equals the baseline again" '[[ $(state) == "$BASELINE" && $(verify) == "F8_VERIFY_PASS full f293e72-f9c2" ]]'
chmod -R u+w "${NEW}"; rm -rf "${NEW}"   # simulation only: discard the staged release before the real run

# --- install -----------------------------------------------------------------------------------------------------
run bash "${INSTALL}" install "$P"; echo "$OUT" | sed 's/^/  | /'
check "install succeeds" '[[ $RC -eq 0 && $OUT == *"COG1_INSTALLED current=f293e72-f9c2-cog1"* ]]'
check "  current is cog1 and verify --full passes" '[[ $(readlink "${BASE}/current") == releases/f293e72-f9c2-cog1 && $(verify) == "F8_VERIFY_PASS full f293e72-f9c2-cog1" ]]'
check "  adapter and PROD module installed root 0644" '[[ $(sha256sum < "${LR}/world_context.py" | cut -c1-16) == 07a763e1dd3d81e8 && $(sha256sum < "${LR}/_prod_world_context.py" | cut -c1-16) == 46b8187e3f6f2ac7 && $(stat -c %a:%U "${LR}/_prod_world_context.py") == 644:root ]]'
check "  cog1 verifier is the cog1 template with the host token" '[[ $(sha256sum < "${NEW}/bin/verify_release.py") == $(render "${COG}/templates/bin/verify_release.py.tmpl" | sha256sum) ]]'
check "  cog1 RELEASE.sha256 verifies and is root read-only" '(cd "${NEW}" && sha256sum -c --quiet RELEASE.sha256) && [[ -z $(find "${NEW}" -perm /222 ! -type l) ]]'
check "  f9c2 release untouched" '[[ $(cd "${OLD}" && sha256sum -c --quiet RELEASE.sha256 && find . -type f -o -type l | LC_ALL=C sort | xargs -d "\n" sha256sum 2>/dev/null | sha256sum | cut -c1-16) == "$OLD_TREE" ]]'
check "  router.yaml unchanged (every lane off)" '[[ $(sha256sum < "${LR}/router.yaml" | cut -c1-16) == 7bb4fbb5cb0db6c7 ]]'
check "  critical pins include the PROD module" 'grep -q "_prod_world_context.py" /etc/hermes-gateway-dev/critical.sha256'
run bash "${INSTALL}" install "$P"; check "second install refuses" '[[ $RC -ne 0 && $OUT == *"current is not f293e72-f9c2"* ]]'

# --- revert --------------------------------------------------------------------------------------------------------
run bash "${INSTALL}" revert "$P"; echo "$OUT" | sed 's/^/  | /'
check "revert succeeds" '[[ $RC -eq 0 && $OUT == *"COG1_REVERTED current=f293e72-f9c2"* ]]'
check "  state equals the f9c2 baseline" '[[ $(state) == "$BASELINE" && $(verify) == "F8_VERIFY_PASS full f293e72-f9c2" ]]'
check "  PROD module moved to backups, not deleted" '[[ $(sha256sum < $(ls -d /var/backups/hermes-gateway-dev/cog1-revert-*/ | tail -1)_prod_world_context.py | cut -c1-16) == 46b8187e3f6f2ac7 ]]'
check "  cog1 release kept" '[[ -d ${NEW} ]]'

echo "SIM_RESULT $([[ ${FAILS} -eq 0 ]] && echo PASS || echo "FAIL (${FAILS})")"
exit "${FAILS}"
