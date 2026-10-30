#!/usr/bin/env bash
# Offline simulation of bin/install_r1.sh on a g1 host built from this repository. TEST_ONLY.
# Run as root on a disposable Linux machine; it re-executes itself in a private mount namespace with overlay
# filesystems on /etc /var /opt /home, so nothing outside a scratch directory is written:
#   sudo bash sim_install_r1.sh <repo-root>
# Builds the f9c2-shaped host of dev-f9c2-cog1/tests/sim_install_cog1.sh, installs cog1, wm1 and then g1 with the merged
# install_cog1.sh, install_wm1.sh and install_g1.sh (as the Gates on DEV did), then exercises install_r1.sh. Real
# pin_critical.sh and real verifiers (synthetic token), a systemctl shim, the FORGET executor's real lock path, and a
# Core API DB at the DEV path that must never change (Reasoning shadow reads and writes nothing). Prints PASS/FAIL per case.
set -Eeuo pipefail
REPO=$(readlink -f "${1:?repo root}")
if [[ -z ${COG1_SIM_INNER:-} ]]; then
  [[ $(id -u) -eq 0 ]] || { echo "run as root"; exit 2; }
  [[ $(hostname) != lilith-* ]] || { echo "refused on $(hostname)"; exit 2; }
  exec env COG1_SIM_INNER=1 unshare -m --propagation private bash "$0" "$REPO"
fi
S=$(mktemp -d /tmp/g2sim.XXXXXX)
for d in etc var opt home; do
  mkdir -p "$S/ov/$d/u" "$S/ov/$d/w"
  mount -t overlay overlay -o "lowerdir=/$d,upperdir=$S/ov/$d/u,workdir=$S/ov/$d/w" "/$d"
done
REL9=${REPO}/integrations/hermes/release/dev-f9c2
COG=${REPO}/integrations/hermes/release/dev-f9c2-cog1
WM1=${REPO}/integrations/hermes/release/dev-f9c2-cog1-wm1
G1R=${REPO}/integrations/hermes/release/dev-f9c2-cog1-wm1-g1
WM=${REPO}/integrations/hermes/release/dev-f9c2-cog1-wm1-g1-r1
INSTALL=${WM}/bin/install_r1.sh
TOKEN="TEST_ONLY-$(printf 'd0%.0s' $(seq 1 20))"
BASE=/opt/hermes-gateway-dev; F9=${BASE}/releases/f293e72-f9c2
COG1=${BASE}/releases/f293e72-f9c2-cog1
WM1REL=${BASE}/releases/f293e72-f9c2-cog1-wm1
OLD=${BASE}/releases/f293e72-f9c2-cog1-wm1-g1; NEW=${BASE}/releases/f293e72-f9c2-cog1-wm1-g1-r1
GDB=/home/lilith/.hermes/lilith-os-dev/data/lilith-dev.db
HH=/home/lilith/.hermes-dev; LR=${HH}/lilith_router
LOCK=/var/lib/hermes-forget/state/.lock; INTENT=/var/lib/hermes-forget/intent
FAILS=0
pass() { echo "PASS $*"; }
fail() { echo "FAIL $*"; FAILS=$((FAILS + 1)); }
check() { if eval "$2"; then pass "$1"; else fail "$1"; echo "$OUT" | tail -5 | sed 's/^/    > /'; fi; }
render() { python3 -I -c 'import sys; sys.stdout.buffer.write(open(sys.argv[1],"rb").read().replace(b"__LILITH_GATE_CLIENT_TOKEN__", sys.argv[2].encode()))' "$1" "$TOKEN"; }

mkdir -p "$S/bin"
cat > "$S/bin/systemctl" <<'SH'
#!/bin/sh
if [ "$1 $2" = "show hermes-gateway-dev" ]; then
  [ "${SIM_GW:-inactive dead 0}" = unknown ] && exit 1
  set -- ${SIM_GW:-inactive dead 0}
  printf 'LoadState=loaded\nActiveState=%s\nSubState=%s\nMainPID=%s\n' "$1" "$2" "$3"; exit 0
fi
echo "sim systemctl refused: $*" >&2; exit 1
SH
chmod 0755 "$S/bin/systemctl"; export PATH="$S/bin:$PATH" F8_SIM=1

# --- f9c2-shaped host (as dev-f9c2-cog1/tests/sim_install_cog1.sh) -----------------------------------------------
id lilith >/dev/null 2>&1 || useradd --system --no-create-home lilith
install -d -m 0755 "${BASE}" "${BASE}/releases" "${F9}" "${F9}/bin" "${F9}/venv/bin"
cp -a "${REL9}/bin/." "${F9}/bin/"
render "${REL9}/templates/bin/verify_release.py.tmpl" > "${F9}/bin/verify_release.py"
for f in gateway/run.py agent/background_review.py tools/memory_tool.py tools/skill_manager_tool.py \
         tools/write_approval.py tools/legacy_canonical_containment.py; do
  install -d "${F9}/src/$(dirname "$f")"; echo "TEST_ONLY src $f" > "${F9}/src/$f"
done
ln -s /usr/bin/python3 "${F9}/venv/bin/python"
printf 'f293e72-f9c2\n' > "${F9}/RELEASE_ID"
(cd "${F9}" && find . -name __pycache__ -prune -o -type f ! -name 'RELEASE.sha256*' -print | sed 's|^\./||' \
  | LC_ALL=C sort | xargs -r -d '\n' sha256sum) > "${F9}/RELEASE.sha256"
chown -R root:root "${F9}"; chmod -R go-w "${F9}"; chmod -R a-w "${F9}"
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
install -d -m 0711 /var/lib/hermes-forget; install -d -m 0700 /var/lib/hermes-forget/state; install -d -m 1770 "${INTENT}"
bash "${F9}/bin/pin_critical.sh" "${F9}" >/dev/null

# --- cog1, installed with the merged installer (as Gate C on DEV) ----------------------------------------------------
P1=$S/payload-cog1; install -d -o root -g root -m 0700 "$P1"
cp "${REPO}/integrations/hermes/overlays/dev-unified-cognition/lilith_router/world_context.py" "$P1/world_context.py"
cp "${REPO}/integrations/hermes/home/variants/prod-lilith-01/lilith_router/world_context.py" "$P1/_prod_world_context.py"
cp "${REPO}/integrations/hermes/home/variants/dev-f9c2/lilith_router/world_context.py" "$P1/world_context.f9c2-stub.py"
cp "${COG}/templates/bin/verify_release.py.tmpl" "$P1/verify_release.cog1.py.tmpl"
cp "${REL9}/templates/bin/verify_release.py.tmpl" "$P1/verify_release.f9c2.py.tmpl"
cp "${COG}/RELEASE_ID" "$P1/RELEASE_ID"
bash "${COG}/bin/install_cog1.sh" install "$P1" >/dev/null 2>&1 || { echo "SIM_SETUP_FAIL cog1 install"; exit 2; }

# --- wm1, installed with the merged installer (as Gate E on DEV) -----------------------------------------------------
P2=$S/payload-wm1; install -d -o root -g root -m 0700 "$P2"
cp "${WM1}/home/router.yaml" "$P2/router.wm1.yaml"
cp "${REPO}/integrations/hermes/home/variants/dev-f9c2/router.yaml" "$P2/router.cog1.yaml"
cp "${WM1}/templates/bin/verify_release.py.tmpl" "$P2/verify_release.wm1.py.tmpl"
cp "${COG}/templates/bin/verify_release.py.tmpl" "$P2/verify_release.cog1.py.tmpl"
cp "${WM1}/RELEASE_ID" "$P2/RELEASE_ID"
bash "${WM1}/bin/install_wm1.sh" install "$P2" >/dev/null 2>&1 || { echo "SIM_SETUP_FAIL wm1 install"; exit 2; }

# --- g1, installed with the merged installer (as Gate E on DEV, 2026-10-30) ------------------------------------------
P3=$S/payload-g1; install -d -o root -g root -m 0700 "$P3"
cp "${G1R}/home/router.yaml" "$P3/router.g1.yaml"
cp "${WM1}/home/router.yaml" "$P3/router.wm1.yaml"
cp "${G1R}/templates/bin/verify_release.py.tmpl" "$P3/verify_release.g1.py.tmpl"
cp "${WM1}/templates/bin/verify_release.py.tmpl" "$P3/verify_release.wm1.py.tmpl"
cp "${G1R}/RELEASE_ID" "$P3/RELEASE_ID"
bash "${G1R}/bin/install_g1.sh" install "$P3" >/dev/null 2>&1 || { echo "SIM_SETUP_FAIL g1 install"; exit 2; }

# --- the Core API DB at the DEV path ----------------------------------------------------------------------------------
install -d -o lilith -g lilith -m 0750 "$(dirname "${GDB}")"
rm -f "${GDB}" "${GDB}-journal" "${GDB}-wal" "${GDB}-shm"   # inside the /home overlay only: start from a fresh file
python3 -I -c 'import sqlite3,sys; c=sqlite3.connect(sys.argv[1]); c.execute("CREATE TABLE world_belief (key TEXT PRIMARY KEY)"); c.commit()' "${GDB}"
chown lilith:lilith "${GDB}"; chmod 0640 "${GDB}"
verify() { "${BASE}/current/venv/bin/python" -I -B "${BASE}/current/bin/verify_release.py" --full 2>&1 | tail -1; }
state() {   # release root (excluding r1 and failed staging), HERMES_HOME and the gateway pins
  find "${BASE}" "${HH}" /etc/hermes-gateway-dev \( -path "${NEW}" -o -name '.r1-failed-staging-*' \) -prune \
    -o \( -type f -o -type l \) -print | LC_ALL=C sort | while read -r p; do
      if [[ -L $p ]]; then echo "L $p -> $(readlink "$p")"; else echo "F $p $(stat -c %a:%U:%G "$p") $(sha256sum < "$p" | cut -c1-16)"; fi
    done | sha256sum | cut -c1-16
}
tree_of() { (cd "$1" && sha256sum -c --quiet RELEASE.sha256 && find . \( -type f -o -type l \) -print | LC_ALL=C sort \
  | xargs -d '\n' sha256sum 2>/dev/null | sha256sum | cut -c1-16); }
payload() {
  install -d -o root -g root -m 0700 "$1"
  cp "${WM}/home/router.yaml" "$1/router.r1.yaml"
  cp "${G1R}/home/router.yaml" "$1/router.g1.yaml"
  cp "${WM}/templates/bin/verify_release.py.tmpl" "$1/verify_release.r1.py.tmpl"
  cp "${G1R}/templates/bin/verify_release.py.tmpl" "$1/verify_release.g1.py.tmpl"
  cp "${WM}/RELEASE_ID" "$1/RELEASE_ID"
}
run() { set +e; OUT=$("$@" 2>&1); RC=$?; set -e; }
discard_new() { [[ -e ${NEW} ]] && { chmod -R u+w "${NEW}"; rm -rf "${NEW}"; } || true; }   # simulation only
quarantined() { find "${BASE}/releases" -maxdepth 1 -name '.r1-failed-staging-*' | wc -l; }
rmode() { python3 -I -c 'import sys,yaml; print(yaml.safe_load(open(sys.argv[1])).get("mode"))' "${LR}/router.yaml"; }
lane() { python3 -I -c 'import sys,yaml; r=yaml.safe_load(open(sys.argv[1])); print(r.get("cognitive_enabled"), r.get("cognitive_mode"), ",".join(r.get("cognitive_channels") or []) or "-")' "${LR}/router.yaml"; }
goals() { python3 -I -c 'import sys,yaml; r=yaml.safe_load(open(sys.argv[1])); print(r.get("goals_enabled"), r.get("goals_mode"))' "${LR}/router.yaml"; }
reasoning() { python3 -I -c 'import sys,yaml; r=yaml.safe_load(open(sys.argv[1])); print(r.get("reasoning_enabled"), r.get("reasoning_mode"))' "${LR}/router.yaml"; }
LOCKPROBE='python3 -I -c "import fcntl,os; fd=os.open(\"/var/lib/hermes-forget/state/.lock\",os.O_RDWR|os.O_CREAT,0o600)
try:
    fcntl.flock(fd, fcntl.LOCK_EX|fcntl.LOCK_NB); print(\"ACQUIRED\")
except BlockingIOError:
    print(\"BLOCKED\")" >> '"$S"'/probe.log'

check "baseline: g1 current, verify --full passes, World Model and Goals shadow, Reasoning off" '[[ $(readlink "${BASE}/current") == releases/f293e72-f9c2-cog1-wm1-g1 && $(verify) == "F8_VERIFY_PASS full f293e72-f9c2-cog1-wm1-g1" && $(lane) == "True shadow lilith_os" && $(goals) == "True shadow" && $(reasoning) == "False None" ]]'
BASELINE=$(state); G1_TREE=$(tree_of "${OLD}"); WM1_TREE=$(tree_of "${WM1REL}"); COG1_TREE=$(tree_of "${COG1}"); F9_TREE=$(tree_of "${F9}")
P=$S/payload; payload "$P"
DB0=$(sha256sum < "${GDB}")

# --- F8_SIM isolation and refusals before any change ----------------------------------------------------------------
for h in lilith-01 lilith-dev-01; do
  run unshare -u bash -c "hostname $h; bash '${INSTALL}' install '$P'"
  check "F8_SIM refused on $h" '[[ $RC -ne 0 && $OUT == *"F8_SIM refused on '"$h"'"* && $(state) == "$BASELINE" ]]'
done
run env -u F8_SIM bash "${INSTALL}" install "$P"; check "without F8_SIM only lilith-dev-01 is accepted" '[[ $RC -ne 0 && $OUT == *"wrong host"* && $(state) == "$BASELINE" ]]'
install -d -o root -g root -m 0700 "$S/p1"; cp "$P"/* "$S/p1/"; echo "# TEST_ONLY" >> "$S/p1/router.r1.yaml"
run bash "${INSTALL}" install "$S/p1"; check "refuses a changed router payload" '[[ $RC -ne 0 && $OUT == *"payload digest router.r1.yaml"* && $(state) == "$BASELINE" ]]'
for gw in "active running 4242" "activating start-pre 0" "deactivating stop-sigterm 4242" "reloading running 4242" unknown; do
  run env SIM_GW="$gw" bash "${INSTALL}" install "$P"
  check "refuses gateway state [$gw]" '[[ $RC -ne 0 && $OUT == *"gateway not fully stopped"* && $(state) == "$BASELINE" ]]'
done
touch "${INTENT}/test.intent"
run bash "${INSTALL}" install "$P"; check "refuses while a FORGET intent is pending" '[[ $RC -ne 0 && $OUT == *"intent present"* && $(state) == "$BASELINE" ]]'
rm -f "${INTENT}/test.intent"
run bash "${INSTALL}" revert "$P"; check "revert refuses when g1 is current and verifies" '[[ $RC -ne 0 && $OUT == *"nothing to revert"* && $(state) == "$BASELINE" ]]'

# --- FORGET races --------------------------------------------------------------------------------------------------
python3 -I -c "import fcntl,os,time; fd=os.open('${LOCK}',os.O_RDWR|os.O_CREAT,0o600); fcntl.flock(fd,fcntl.LOCK_EX); open('$S/held','w').close(); time.sleep(45)" &
HOLDER=$!; while [[ ! -e $S/held ]]; do sleep 0.1; done
run bash "${INSTALL}" install "$P"; kill "${HOLDER}" 2>/dev/null || true; wait "${HOLDER}" 2>/dev/null || true
check "a held FORGET lock blocks the install (no change)" '[[ $RC -ne 0 && $OUT == *"FORGET executor busy"* && $(state) == "$BASELINE" && ! -e ${NEW} ]]'
run env F8_PROBE_AT=staged F8_PROBE_CMD="touch ${INTENT}/race.intent" bash "${INSTALL}" install "$P"
check "an intent arriving after staging stops the install before any HERMES_HOME change" '[[ $RC -ne 0 && $OUT == *"intent present"* && $(state) == "$BASELINE" && ! -e ${NEW} && $(quarantined) -eq 1 ]]'
rm -f "${INTENT}/race.intent"; : > "$S/probe.log"
run env F8_PROBE_AT=after_home F8_PROBE_CMD="${LOCKPROBE}" bash "${INSTALL}" install "$P"
check "the executor cannot take the lock while router.yaml is replaced" '[[ $RC -eq 0 && $(cat $S/probe.log) == BLOCKED ]]'
: > "$S/probe.log"
run env F8_PROBE_AT=revert_after_router F8_PROBE_CMD="${LOCKPROBE}" bash "${INSTALL}" revert "$P"
check "the executor cannot take the lock during a revert" '[[ $RC -eq 0 && $(cat $S/probe.log) == BLOCKED && $OUT == *R1_REVERTED* && $(state) == "$BASELINE" ]]'
discard_new

# --- staging failure and automatic revert ---------------------------------------------------------------------------
run env F8_FAIL_AT=staging bash "${INSTALL}" install "$P"
check "staging failure keeps the partial release under a new name, changes nothing else" '[[ $RC -ne 0 && $OUT == *"partial release kept"* && $(state) == "$BASELINE" && ! -e ${NEW} && $(quarantined) -eq 2 ]]'
for at in after_home after_switch; do
  run env F8_FAIL_AT=$at bash "${INSTALL}" install "$P"
  check "injected failure at $at reverts to the g1 baseline" '[[ $RC -ne 0 && $OUT == *"INJECTED_FAILURE at '"$at"'"* && $OUT == *R1_REVERTED* && $(state) == "$BASELINE" && $(verify) == "F8_VERIFY_PASS full f293e72-f9c2-cog1-wm1-g1" ]]'
  discard_new
done

# --- install -----------------------------------------------------------------------------------------------------
run bash "${INSTALL}" install "$P"
check "install succeeds" '[[ $RC -eq 0 && $OUT == *"R1_INSTALLED current=f293e72-f9c2-cog1-wm1-g1-r1"* ]]'
check "  current is r1 and verify --full passes" '[[ $(readlink "${BASE}/current") == releases/f293e72-f9c2-cog1-wm1-g1-r1 && $(verify) == "F8_VERIFY_PASS full f293e72-f9c2-cog1-wm1-g1-r1" ]]'
check "  router.yaml is the r1 one, root:lilith 0640, World Model, Goals and Reasoning shadow on lilith_os, router mode shadow" '[[ $(sha256sum < "${LR}/router.yaml" | cut -c1-64) == $(sha256sum < "${WM}/home/router.yaml" | cut -c1-64) && $(stat -c %a:%U:%G "${LR}/router.yaml") == 640:root:lilith && $(lane) == "True shadow lilith_os" && $(goals) == "True shadow" && $(reasoning) == "True shadow" && $(rmode) == shadow ]]'
check "  adapter and PROD module unchanged" '[[ $(sha256sum < "${LR}/world_context.py" | cut -c1-16) == 07a763e1dd3d81e8 && $(sha256sum < "${LR}/_prod_world_context.py" | cut -c1-16) == 46b8187e3f6f2ac7 ]]'
check "  r1 verifier is the r1 template with the host token" '[[ $(sha256sum < "${NEW}/bin/verify_release.py") == $(render "${WM}/templates/bin/verify_release.py.tmpl" | sha256sum) ]]'
check "  g1, wm1, cog1 and f9c2 releases untouched; the DB file unchanged" '[[ $(tree_of "${OLD}") == "$G1_TREE" && $(tree_of "${WM1REL}") == "$WM1_TREE" && $(tree_of "${COG1}") == "$COG1_TREE" && $(tree_of "${F9}") == "$F9_TREE" && $(sha256sum < "${GDB}") == "$DB0" ]]'
check "  the installed g1 verifier refuses the r1 router (Reasoning on)" '[[ $("${OLD}/venv/bin/python" -I -B "${OLD}/bin/verify_release.py" --full 2>&1) == *"LANE_NOT_OFF reasoning_enabled"* ]]'
run bash "${INSTALL}" install "$P"; check "second install refuses" '[[ $RC -ne 0 && $OUT == *"current is not f293e72-f9c2-cog1-wm1-g1"* ]]'

# --- revert failures and resumption -------------------------------------------------------------------------------
for at in revert_after_router revert_after_switch; do
  run env F8_FAIL_AT=$at bash "${INSTALL}" revert "$P"
  check "revert failing at $at reports R1_REVERT_FAIL" '[[ $RC -ne 0 && $OUT == *"INJECTED_FAILURE at '"$at"'"* && $OUT == *R1_REVERT_FAIL* ]]'
  run bash "${INSTALL}" revert "$P"
  check "  re-running revert completes to the g1 baseline" '[[ $RC -eq 0 && $OUT == *R1_REVERTED* && $(state) == "$BASELINE" && $(verify) == "F8_VERIFY_PASS full f293e72-f9c2-cog1-wm1-g1" ]]'
  discard_new
  run bash "${INSTALL}" install "$P"; [[ $RC -eq 0 ]] || fail "  re-install after $at"
done
run env SIM_GW="failed failed 0" bash "${INSTALL}" revert "$P"
check "revert succeeds with the gateway in failed/failed; World Model and Goals shadow, Reasoning off again" '[[ $RC -eq 0 && $OUT == *"R1_REVERTED current=f293e72-f9c2-cog1-wm1-g1"* && $(state) == "$BASELINE" && $(lane) == "True shadow lilith_os" && $(goals) == "True shadow" && $(reasoning) == "False None" && $(sha256sum < "${GDB}") == "$DB0" ]]'
check "  r1 release kept for inspection" '[[ -d ${NEW} ]]'

# --- the documented further rollback steps: install_g1.sh revert -> wm1, then install_wm1.sh revert -> cog1 ---------
run bash "${G1R}/bin/install_g1.sh" revert "$P3"
check "install_g1.sh revert then returns to wm1 (World Model shadow, Goals off)" '[[ $RC -eq 0 && $OUT == *"G1_REVERTED current=f293e72-f9c2-cog1-wm1"* && $(verify) == "F8_VERIFY_PASS full f293e72-f9c2-cog1-wm1" && $(lane) == "True shadow lilith_os" && $(goals) == "False None" ]]'

run bash "${WM1}/bin/install_wm1.sh" revert "$P2"
check "install_wm1.sh revert then returns to cog1 with every lane off" '[[ $RC -eq 0 && $OUT == *"WM1_REVERTED current=f293e72-f9c2-cog1"* && $(verify) == "F8_VERIFY_PASS full f293e72-f9c2-cog1" && $(lane) == "False None -" ]]'

echo "SIM_RESULT $([[ ${FAILS} -eq 0 ]] && echo PASS || echo "FAIL (${FAILS})")"
exit "${FAILS}"
