#!/usr/bin/env bash
# Offline simulation of bin/install_gv1.sh. TEST_ONLY. Run as root on a disposable Linux machine (not lilith-*); it re-executes
# itself in a private mount namespace with overlay filesystems on /etc /var /opt /home, so nothing outside a scratch
# directory is written:   sudo bash sim_install_gv1.sh <repo-root>
# The host chain (f9c2 -> cog1 -> wm1 -> g1 -> r1 -> w1 -> m1 -> p1) is the e1 simulation's, copied unchanged from
# dev-...-e1/tests/sim_install_e1.sh; then e1 is installed with the merged install_e1.sh, and the goal store is given
# DEV's 2026-11-10 shape (six terminal TEST_ONLY commitment goals, 20 transition traces), so e1 refuses exactly as DEV
# does. A fake Core API laid out like DEV's (api-venv/bin/uvicorn app:app, cwd releases/<sha>/ holding this repo's
# app.py, LILITH_DB_PATH, LILITH_OS_FOCUS_READ_ONLY) answers GET /os/goals/focus on 127.0.0.1:8765 and writes an
# arbitration trace on a changed winner unless the flag is 1, like app.py. A systemctl shim is bind-mounted over
# /usr/bin/systemctl inside the namespace. Prints PASS/FAIL per case.
set -Eeuo pipefail
REPO=$(readlink -f "${1:?repo root}")
if [[ -z ${COG1_SIM_INNER:-} ]]; then
  [[ $(id -u) -eq 0 ]] || { echo "run as root"; exit 2; }
  [[ $(hostname) != lilith-* ]] || { echo "refused on $(hostname)"; exit 2; }
  exec env COG1_SIM_INNER=1 unshare -m --propagation private bash "$0" "$REPO"
fi
S=$(mktemp -d /tmp/gv1sim.XXXXXX)
for d in etc var opt home; do
  mkdir -p "$S/ov/$d/u" "$S/ov/$d/w"
  mount -t overlay overlay -o "lowerdir=/$d,upperdir=$S/ov/$d/u,workdir=$S/ov/$d/w" "/$d"
done
REL9=${REPO}/integrations/hermes/release/dev-f9c2
COG=${REPO}/integrations/hermes/release/dev-f9c2-cog1
WM1=${REPO}/integrations/hermes/release/dev-f9c2-cog1-wm1
G1R=${REPO}/integrations/hermes/release/dev-f9c2-cog1-wm1-g1
R1R=${REPO}/integrations/hermes/release/dev-f9c2-cog1-wm1-g1-r1
W1R=${REPO}/integrations/hermes/release/dev-f9c2-cog1-wm1-g1-r1-w1
M1R=${REPO}/integrations/hermes/release/dev-f9c2-cog1-wm1-g1-r1-w1-m1
P1R=${REPO}/integrations/hermes/release/dev-f9c2-cog1-wm1-g1-r1-w1-m1-p1
WM=${REPO}/integrations/hermes/release/dev-f9c2-cog1-wm1-g1-r1-w1-m1-p1-e1
INSTALL=${WM}/bin/install_e1.sh
TOKEN="TEST_ONLY-$(printf 'd0%.0s' $(seq 1 20))"
BASE=/opt/hermes-gateway-dev; F9=${BASE}/releases/f293e72-f9c2
COG1=${BASE}/releases/f293e72-f9c2-cog1
WM1REL=${BASE}/releases/f293e72-f9c2-cog1-wm1
G1REL=${BASE}/releases/f293e72-f9c2-cog1-wm1-g1; R1REL=${BASE}/releases/f293e72-f9c2-cog1-wm1-g1-r1; W1REL=${BASE}/releases/f293e72-f9c2-cog1-wm1-g1-r1-w1; M1REL=${BASE}/releases/f293e72-f9c2-cog1-wm1-g1-r1-w1-m1; OLD=${BASE}/releases/f293e72-f9c2-cog1-wm1-g1-r1-w1-m1-p1; NEW=${BASE}/releases/f293e72-f9c2-cog1-wm1-g1-r1-w1-m1-p1-e1
GDB=/home/lilith/.hermes/lilith-os-dev/data/lilith-dev.db
HH=/home/lilith/.hermes-dev; LR=${HH}/lilith_router
LOCK=/var/lib/hermes-forget/state/.lock; INTENT=/var/lib/hermes-forget/intent
FAILS=0; OUT=
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

# --- r1, installed with the merged installer ----------------------------------------------------------------------
P4=$S/payload-r1; install -d -o root -g root -m 0700 "$P4"
cp "${R1R}/home/router.yaml" "$P4/router.r1.yaml"; cp "${G1R}/home/router.yaml" "$P4/router.g1.yaml"
cp "${R1R}/templates/bin/verify_release.py.tmpl" "$P4/verify_release.r1.py.tmpl"; cp "${G1R}/templates/bin/verify_release.py.tmpl" "$P4/verify_release.g1.py.tmpl"
cp "${R1R}/RELEASE_ID" "$P4/RELEASE_ID"
bash "${R1R}/bin/install_r1.sh" install "$P4" >/dev/null 2>&1 || { echo "SIM_SETUP_FAIL r1 install"; exit 2; }

# --- the Core API DB at the DEV path ----------------------------------------------------------------------------------
install -d -o lilith -g lilith -m 0750 "$(dirname "${GDB}")"
rm -f "${GDB}" "${GDB}-journal" "${GDB}-wal" "${GDB}-shm"   # inside the /home overlay only: start from a fresh file
python3 -I -c 'import sqlite3,sys; c=sqlite3.connect(sys.argv[1]); c.execute("CREATE TABLE world_belief (key TEXT PRIMARY KEY)"); c.commit()' "${GDB}"
chown lilith:lilith "${GDB}"; chmod 0640 "${GDB}"
verify() { "${BASE}/current/venv/bin/python" -I -B "${BASE}/current/bin/verify_release.py" --full 2>&1 | tail -1; }
state() {   # release root (excluding w1 and failed staging), HERMES_HOME and the gateway pins
  find "${BASE}" "${HH}" /etc/hermes-gateway-dev \( -path "${NEW}" -o -name '.e1-failed-staging-*' \) -prune \
    -o \( -type f -o -type l \) -print | LC_ALL=C sort | while read -r p; do
      if [[ -L $p ]]; then echo "L $p -> $(readlink "$p")"; else echo "F $p $(stat -c %a:%U:%G "$p") $(sha256sum < "$p" | cut -c1-16)"; fi
    done | sha256sum | cut -c1-16
}
tree_of() { (cd "$1" && sha256sum -c --quiet RELEASE.sha256 && find . \( -type f -o -type l \) -print | LC_ALL=C sort \
  | xargs -d '\n' sha256sum 2>/dev/null | sha256sum | cut -c1-16); }
payload() {
  install -d -o root -g root -m 0700 "$1"
  cp "${WM}/home/router.yaml" "$1/router.e1.yaml"
  cp "${P1R}/home/router.yaml" "$1/router.p1.yaml"
  cp "${WM}/templates/bin/verify_release.py.tmpl" "$1/verify_release.e1.py.tmpl"
  cp "${P1R}/templates/bin/verify_release.py.tmpl" "$1/verify_release.p1.py.tmpl"
  cp "${WM}/RELEASE_ID" "$1/RELEASE_ID"
  cp "${REPO}/integrations/hermes/overlays/dev-ethics-hardening/lilith_router/ethics.py" "$1/ethics.e1.py"
  cp "${REPO}/docs/architecture/slice-13/ethics.py" "$1/ethics.p1.py"
  cp "${REPO}/integrations/hermes/overlays/dev-ethics-hardening/lilith_router/world_context.py" "$1/world_context.e1.py"
  cp "${REPO}/integrations/hermes/overlays/dev-cognition-private-intent/lilith_router/world_context.py" "$1/world_context.p1.py"
}
run() { set +e; OUT=$("$@" 2>&1); RC=$?; set -e; }
discard_new() { [[ -e ${NEW} ]] && { chmod -R u+w "${NEW}"; rm -rf "${NEW}"; } || true; }   # simulation only
quarantined() { find "${BASE}/releases" -maxdepth 1 -name '.e1-failed-staging-*' | wc -l; }
rmode() { python3 -I -c 'import sys,yaml; print(yaml.safe_load(open(sys.argv[1])).get("mode"))' "${LR}/router.yaml"; }
lane() { python3 -I -c 'import sys,yaml; r=yaml.safe_load(open(sys.argv[1])); print(r.get("cognitive_enabled"), r.get("cognitive_mode"), ",".join(r.get("cognitive_channels") or []) or "-")' "${LR}/router.yaml"; }
goals() { python3 -I -c 'import sys,yaml; r=yaml.safe_load(open(sys.argv[1])); print(r.get("goals_enabled"), r.get("goals_mode"))' "${LR}/router.yaml"; }
wspace() { python3 -I -c 'import sys,yaml; r=yaml.safe_load(open(sys.argv[1])); print(r.get("ethics_enabled"), r.get("ethics_mode"))' "${LR}/router.yaml"; }
tables() { python3 -I -c 'import sqlite3,sys; c=sqlite3.connect("file:%s?mode=ro" % sys.argv[1], uri=True); print(",".join(n for (n,) in c.execute("SELECT name FROM sqlite_master WHERE type=? AND name IN (?,?,?) ORDER BY name", ("table","drafts","goal","goal_trace"))) or "-")' "${GDB}"; }
bootstrap_schema() {   # stands in for the separately approved gates: the Core API's own DDL from app.py
  python3 -I - "${REPO}/services/core-api/app.py" "${GDB}" <<'PY'
import sqlite3, sys
Q = chr(34) * 3
app = open(sys.argv[1], encoding="utf-8").read()
goal = app.split("def _goals_db():", 1)[1].split("conn.executescript(", 1)[1].split(Q, 2)[1]
dr = app.split("def _drafts_db():", 1)[1].split("return conn", 1)[0]
stmts = [p.split(Q, 2)[1] if Q in p else p.split('"', 2)[1] for p in dr.split("conn.execute(")[1:]]
c = sqlite3.connect(sys.argv[2]); c.executescript(goal)
for st in stmts:
    c.execute(st)
c.commit(); c.close()
PY
}
reasoning() { python3 -I -c 'import sys,yaml; r=yaml.safe_load(open(sys.argv[1])); print(r.get("reasoning_enabled"), r.get("reasoning_mode"))' "${LR}/router.yaml"; }
LOCKPROBE='python3 -I -c "import fcntl,os; fd=os.open(\"/var/lib/hermes-forget/state/.lock\",os.O_RDWR|os.O_CREAT,0o600)
try:
    fcntl.flock(fd, fcntl.LOCK_EX|fcntl.LOCK_NB); print(\"ACQUIRED\")
except BlockingIOError:
    print(\"BLOCKED\")" >> '"$S"'/probe.log'

# --- w1, installed with the merged installer, on the bootstrapped schema ---------------------------------------------
bootstrap_schema
P5=$S/payload-w1; install -d -o root -g root -m 0700 "$P5"
cp "${W1R}/home/router.yaml" "$P5/router.w1.yaml"; cp "${R1R}/home/router.yaml" "$P5/router.r1.yaml"
cp "${W1R}/templates/bin/verify_release.py.tmpl" "$P5/verify_release.w1.py.tmpl"; cp "${R1R}/templates/bin/verify_release.py.tmpl" "$P5/verify_release.r1.py.tmpl"
cp "${W1R}/RELEASE_ID" "$P5/RELEASE_ID"
cp "${REPO}/integrations/hermes/overlays/dev-reasoning-hardening/lilith_router/world_context.py" "$P5/world_context.w1.py"
cp "${REPO}/integrations/hermes/overlays/dev-unified-cognition/lilith_router/world_context.py" "$P5/world_context.r1.py"
cp "${REPO}/integrations/hermes/overlays/dev-workspace-private-trace/lilith_router/workspace.py" "$P5/workspace.w1.py"
cp "${REPO}/integrations/hermes/home/lilith_router/workspace.py" "$P5/workspace.r1.py"
bash "${W1R}/bin/install_w1.sh" install "$P5" >/dev/null 2>&1 || { echo "SIM_SETUP_FAIL w1 install"; exit 2; }
install -m 0644 "${REPO}/docs/architecture/slice-11/motivation.py" "${LR}/motivation.py"
bash "${W1REL}/bin/pin_critical.sh" "${W1REL}" >/dev/null

# --- m1, installed with the merged installer, as on DEV ---------------------------------------------------------------
P6=$S/payload-m1; install -d -o root -g root -m 0700 "$P6"
cp "${M1R}/home/router.yaml" "$P6/router.m1.yaml"; cp "${W1R}/home/router.yaml" "$P6/router.w1.yaml"
cp "${M1R}/templates/bin/verify_release.py.tmpl" "$P6/verify_release.m1.py.tmpl"; cp "${W1R}/templates/bin/verify_release.py.tmpl" "$P6/verify_release.w1.py.tmpl"
cp "${M1R}/RELEASE_ID" "$P6/RELEASE_ID"
cp "${REPO}/integrations/hermes/overlays/dev-motivation-private-trace/lilith_router/motivation.py" "$P6/motivation.m1.py"
cp "${REPO}/docs/architecture/slice-11/motivation.py" "$P6/motivation.w1.py"
bash "${M1R}/bin/install_m1.sh" install "$P6" >/dev/null 2>&1 || { echo "SIM_SETUP_FAIL m1 install"; exit 2; }
install -m 0644 "${REPO}/docs/architecture/slice-12/planning.py" "${LR}/planning.py"
bash "${M1REL}/bin/pin_critical.sh" "${M1REL}" >/dev/null

# --- p1, installed with the merged installer, as on DEV ---------------------------------------------------------------
P7=$S/payload-p1; install -d -o root -g root -m 0700 "$P7"
cp "${P1R}/home/router.yaml" "$P7/router.p1.yaml"; cp "${M1R}/home/router.yaml" "$P7/router.m1.yaml"
cp "${P1R}/templates/bin/verify_release.py.tmpl" "$P7/verify_release.p1.py.tmpl"; cp "${M1R}/templates/bin/verify_release.py.tmpl" "$P7/verify_release.m1.py.tmpl"
cp "${P1R}/RELEASE_ID" "$P7/RELEASE_ID"
cp "${REPO}/integrations/hermes/overlays/dev-planning-hardening/lilith_router/planning.py" "$P7/planning.p1.py"
cp "${REPO}/docs/architecture/slice-12/planning.py" "$P7/planning.m1.py"
cp "${REPO}/integrations/hermes/overlays/dev-cognition-private-intent/lilith_router/world_context.py" "$P7/world_context.p1.py"
cp "${REPO}/integrations/hermes/overlays/dev-reasoning-hardening/lilith_router/world_context.py" "$P7/world_context.m1.py"
bash "${P1R}/bin/install_p1.sh" install "$P7" >/dev/null 2>&1 || { echo "SIM_SETUP_FAIL p1 install"; exit 2; }
install -m 0644 "${REPO}/docs/architecture/slice-13/ethics.py" "${LR}/ethics.py"
install -m 0644 "${REPO}/docs/architecture/slice-13/ethics_principles.py" "${LR}/ethics_principles.py"
bash "${OLD}/bin/pin_critical.sh" "${OLD}" >/dev/null


# --- e1, installed with the merged installer, as on DEV (2026-10-31) ---------------------------------------------------
check "baseline: p1 current and verifies" '[[ $(readlink "${BASE}/current") == releases/f293e72-f9c2-cog1-wm1-g1-r1-w1-m1-p1 && $(verify) == "F8_VERIFY_PASS full f293e72-f9c2-cog1-wm1-g1-r1-w1-m1-p1" ]]'
PE1=$S/payload-e1; payload "$PE1"
bash "${INSTALL}" install "$PE1" >/dev/null 2>&1 || { echo "SIM_SETUP_FAIL e1 install"; exit 2; }
E1REL=${NEW}

# --- DEV's goal store shape: six terminal TEST_ONLY commitment goals, 20 transition traces --------------------------
python3 -I - "${GDB}" <<'PY'
import sqlite3, sys
c = sqlite3.connect(sys.argv[1])
for i, st in enumerate(("COMPLETED", "COMPLETED", "FAILED", "FAILED", "CANCELLED", "CANCELLED")):
    c.execute("INSERT INTO goal (goal_id, schema_version, type, title, source, owner, lifecycle_state, priority, created_at, updated_at, revision) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
              (f"g.test-only-{i}", 1, "commitment.once", "TEST_ONLY", "SCHEDULED", "user", st, "NORMAL", "a", "a", 3))
for i in range(20):
    c.execute("INSERT INTO goal_trace (correlation_id, goal_id, at, kind, source) VALUES (?,?,?,?,?)", (f"c{i}", f"g.test-only-{i % 6}", "a", "transition", "SCHEDULED"))
c.commit()
PY
check "DEV state reproduced: e1 refuses with exactly GOAL_STORE_NOT_EMPTY" '[[ $(verify) == "F8_VERIFY_FAIL GOAL_STORE_NOT_EMPTY" && $("${BASE}/current/venv/bin/python" -I -B "${BASE}/current/bin/verify_release.py" --full 2>&1 | wc -l) -eq 1 ]]'

# --- the fake Core API, laid out like DEV's ------------------------------------------------------------------------
API=/home/lilith/.hermes/lilith-os-dev; APIREL=${API}/releases/edf5c1b5bc910bc03fc0b25647d4e8aa3374c44c
install -d "${API}/api-venv/bin" "${APIREL}"
cp "${REPO}/services/core-api/app.py" "${APIREL}/app.py"; touch -d '-1 min' "${APIREL}/app.py"
cat > "${API}/api-venv/bin/uvicorn" <<'PY'
import json, os, sqlite3
from http.server import BaseHTTPRequestHandler, HTTPServer
DB = os.environ["LILITH_DB_PATH"]
class H(BaseHTTPRequestHandler):
    def log_message(self, *a): pass
    def do_GET(self):
        c = sqlite3.connect(DB)
        cands = c.execute("SELECT goal_id FROM goal WHERE lifecycle_state IN ('ACTIVE','PENDING') ORDER BY goal_id").fetchall()
        winner = cands[0][0] if cands else None
        last = c.execute("SELECT arbitration_winner FROM goal_trace WHERE kind='arbitration' ORDER BY id DESC LIMIT 1").fetchone()
        if os.environ.get("LILITH_OS_FOCUS_READ_ONLY") != "1" and winner != (last[0] if last else None):
            c.execute("INSERT INTO goal_trace (correlation_id, at, kind, arbitration_winner) VALUES ('g_arb','a','arbitration',?)", (winner,))
            c.commit()
        c.close()
        body = json.dumps({"focus": None if winner is None else {"goalId": winner}, "arbitration": {"winner": winner}}).encode()
        self.send_response(200); self.send_header("Content-Type", "application/json"); self.end_headers(); self.wfile.write(body)
HTTPServer(("127.0.0.1", 8765), H).serve_forever()
PY
api_start() {   # $1: value for LILITH_OS_FOCUS_READ_ONLY ("" = unset)
  api_stop
  (cd "${APIREL}" && exec env -i PATH=/usr/bin:/bin LILITH_DB_PATH="${GDB}" ${1:+LILITH_OS_FOCUS_READ_ONLY=$1} \
     python3 "${API}/api-venv/bin/uvicorn" app:app --host 0.0.0.0 --port 8765) &
  echo $! > "$S/api.pid"
  for _ in $(seq 50); do python3 -I -c 'import socket; socket.create_connection(("127.0.0.1", 8765), 0.2)' 2>/dev/null && return 0; sleep 0.1; done
  echo "SIM_SETUP_FAIL fake Core API did not start"; exit 2
}
api_stop() { [[ -s $S/api.pid ]] && { kill "$(cat "$S/api.pid")" 2>/dev/null || true; wait "$(cat "$S/api.pid")" 2>/dev/null || true; }; : > "$S/api.pid"; }
trap api_stop EXIT
cat > "$S/bin/systemctl" <<SH
#!/bin/sh
if [ "\$1 \$2" = "show hermes-gateway-dev" ]; then
  [ "\${SIM_GW:-inactive dead 0}" = unknown ] && exit 1
  set -- \${SIM_GW:-inactive dead 0}
  printf 'LoadState=loaded\nActiveState=%s\nSubState=%s\nMainPID=%s\n' "\$1" "\$2" "\$3"; exit 0
fi
if [ "\$1 \$2" = "show lilith-os-api-dev.service" ]; then
  pid=\$(cat "$S/api.pid" 2>/dev/null); [ -n "\$pid" ] && kill -0 "\$pid" 2>/dev/null || pid=0
  [ "\$pid" = 0 ] && st=inactive || st=active
  printf 'ActiveState=%s\nMainPID=%s\nEnvironment=%s\n' "\$st" "\$pid" "\${SIM_API_UNIT_ENV-HOME=/home/lilith LILITH_DB_PATH=${GDB} LILITH_OS_FOCUS_READ_ONLY=1}"; exit 0
fi
echo "sim systemctl refused: \$*" >&2; exit 1
SH
chmod 0755 "$S/bin/systemctl"
[[ -f /usr/bin/systemctl ]] || { echo "SIM_SETUP_FAIL /usr/bin/systemctl missing (bind target)"; exit 2; }
mount --bind "$S/bin/systemctl" /usr/bin/systemctl   # private namespace only
api_start 1

GV=${REPO}/integrations/hermes/release/dev-f9c2-cog1-wm1-g1-r1-w1-m1-p1-e1-gv1
GVI=${GV}/bin/install_gv1.sh
GVREL=${BASE}/releases/f293e72-f9c2-cog1-wm1-g1-r1-w1-m1-p1-e1-gv1
state() {   # release root (excluding gv1 and failed staging), HERMES_HOME and the gateway pins
  find "${BASE}" "${HH}" /etc/hermes-gateway-dev \( -path "${GVREL}" -o -name '.gv1-failed-staging-*' -o -name '.e1-failed-staging-*' \) -prune \
    -o \( -type f -o -type l \) -print | LC_ALL=C sort | while read -r p; do
      if [[ -L $p ]]; then echo "L $p -> $(readlink "$p")"; else echo "F $p $(stat -c %a:%U:%G "$p") $(sha256sum < "$p" | cut -c1-16)"; fi
    done | sha256sum | cut -c1-16
}
homestate() { find "${HH}" \( -type f -o -type l \) ! -path '*/__pycache__/*' -print | LC_ALL=C sort | xargs -d '\n' sha256sum | sha256sum | cut -c1-16; }
goalrows() { python3 -I -c 'import sqlite3,sys; c=sqlite3.connect("file:%s?mode=ro" % sys.argv[1], uri=True); print(c.execute("SELECT group_concat(goal_id||lifecycle_state||revision) FROM (SELECT * FROM goal ORDER BY goal_id)").fetchone()[0], c.execute("SELECT COUNT(*), SUM(kind=?) FROM goal_trace", ("arbitration",)).fetchone())' "${GDB}"; }
gquarantined() { find "${BASE}/releases" -maxdepth 1 -name '.gv1-failed-staging-*' | wc -l; }
gpayload() {
  install -d -o root -g root -m 0700 "$1"
  cp "${GV}/templates/bin/verify_release.py.tmpl" "$1/verify_release.gv1.py.tmpl"
  cp "${WM}/templates/bin/verify_release.py.tmpl" "$1/verify_release.e1.py.tmpl"
  cp "${WM}/home/router.yaml" "$1/router.e1.yaml"
  cp "${GV}/RELEASE_ID" "$1/RELEASE_ID"
}
discard_gv() { [[ -e ${GVREL} ]] && { chmod -R u+w "${GVREL}"; rm -rf "${GVREL}"; } || true; }   # simulation only
prestart() { "${BASE}/current/venv/bin/python" -I -B "${BASE}/current/bin/verify_release.py" --pre-start 2>&1; }
sqlx() { python3 -I -c 'import sqlite3,sys; c=sqlite3.connect(sys.argv[1]); c.execute(sys.argv[2]); c.commit()' "${GDB}" "$1"; }

GP=$S/payload-gv1; gpayload "$GP"
BASELINE=$(state); HOME0=$(homestate); ROWS0=$(goalrows); E1_TREE=$(tree_of "${E1REL}"); P1_TREE=$(tree_of "${OLD}")
check "e1 baseline: e1 current, gateway stopped, goal rows as DEV" '[[ $(readlink "${BASE}/current") == releases/f293e72-f9c2-cog1-wm1-g1-r1-w1-m1-p1-e1 && $ROWS0 == *"(20, 0)" ]]'

# --- refusals before any change ---------------------------------------------------------------------------------------
for h in lilith-01 lilith-dev-01; do
  run unshare -u bash -c "hostname $h; bash '${GVI}' install '$GP'"
  check "F8_SIM refused on $h" '[[ $RC -ne 0 && $OUT == *"F8_SIM refused on '"$h"'"* && $(state) == "$BASELINE" ]]'
done
run env -u F8_SIM bash "${GVI}" install "$GP"; check "without F8_SIM only lilith-dev-01 is accepted" '[[ $RC -ne 0 && $OUT == *"wrong host"* && $(state) == "$BASELINE" ]]'
install -d -o root -g root -m 0700 "$S/gt"; cp "$GP"/* "$S/gt/"; echo "# TEST_ONLY" >> "$S/gt/verify_release.gv1.py.tmpl"
run bash "${GVI}" install "$S/gt"; check "refuses a changed verifier payload" '[[ $RC -ne 0 && $OUT == *"payload digest verify_release.gv1.py.tmpl"* && $(state) == "$BASELINE" ]]'
install -d -o root -g root -m 0700 "$S/gx"; cp "$GP"/* "$S/gx/"; touch "$S/gx/extra"
run bash "${GVI}" install "$S/gx"; check "refuses an extra payload file" '[[ $RC -ne 0 && $OUT == *"exactly the payload files"* && $(state) == "$BASELINE" ]]'
for gw in "active running 4242" "activating start-pre 0" unknown; do
  run env SIM_GW="$gw" bash "${GVI}" install "$GP"
  check "refuses gateway state [$gw]" '[[ $RC -ne 0 && $OUT == *"gateway not fully stopped"* && $(state) == "$BASELINE" ]]'
done
touch "${INTENT}/test.intent"
run bash "${GVI}" install "$GP"; check "refuses while a FORGET intent is pending" '[[ $RC -ne 0 && $OUT == *"intent present"* && $(state) == "$BASELINE" ]]'
rm -f "${INTENT}/test.intent"
python3 -I -c "import fcntl,os,time; fd=os.open('${LOCK}',os.O_RDWR|os.O_CREAT,0o600); fcntl.flock(fd,fcntl.LOCK_EX); open('$S/gheld','w').close(); time.sleep(45)" &
HOLDER=$!; while [[ ! -e $S/gheld ]]; do sleep 0.1; done
run bash "${GVI}" install "$GP"; kill "${HOLDER}" 2>/dev/null || true; wait "${HOLDER}" 2>/dev/null || true
check "a held FORGET lock blocks the install" '[[ $RC -ne 0 && $OUT == *"FORGET executor busy"* && $(state) == "$BASELINE" ]]'
cp "${HH}/cron/jobs.json" "$S/jobs.bak"; chmod u+w "${HH}/cron/jobs.json"; printf '{"jobs": [1]}\n' > "${HH}/cron/jobs.json"
run bash "${GVI}" install "$GP"; check "refuses when e1 refuses for another reason too" '[[ $RC -ne 0 && $OUT == *"refuses for another reason"* ]]'
cp "$S/jobs.bak" "${HH}/cron/jobs.json"; chmod 0644 "${HH}/cron/jobs.json"
check "  restored" '[[ $(state) == "$BASELINE" ]]'
run bash "${GVI}" revert "$GP"; check "revert refuses when e1 is current" '[[ $RC -ne 0 && $OUT == *"nothing to revert"* && $(state) == "$BASELINE" ]]'

# --- the dry run of the staged gv1 verifier refuses unsafe hosts before any shared change -----------------------------
NQ=0
dry_refuses() {   # $1 case label, $2 expected verifier code
  run bash "${GVI}" install "$GP"; NQ=$((NQ + 1))
  check "dry run refuses: $1" '[[ $RC -ne 0 && $OUT == *"refuses this host (dry run)"* && $OUT == *"'"$2"'"* && $(state) == "$BASELINE" && ! -e ${GVREL} && $(gquarantined) -eq '"$NQ"' ]]'
}
api_start ""; dry_refuses "Core API without the flag" FOCUS_READ_ONLY_NOT_IN_EFFECT
api_start 0; dry_refuses "Core API with the flag disabled" FOCUS_READ_ONLY_NOT_IN_EFFECT
api_start 1
SIM_API_UNIT_ENV="HOME=/home/lilith" dry_refuses "flag not persistent in the unit" FOCUS_READ_ONLY_NOT_PERSISTENT
api_stop; dry_refuses "Core API down (after the bounded wait)" CORE_API_NOT_RUNNING
api_start 1
sqlx "UPDATE goal SET lifecycle_state='ACTIVE' WHERE goal_id='g.test-only-0'"; dry_refuses "an ACTIVE goal" "GOAL_FOCUS_CANDIDATE ACTIVE 1"
sqlx "UPDATE goal SET lifecycle_state='PENDING' WHERE goal_id='g.test-only-0'"; dry_refuses "a PENDING goal" "GOAL_FOCUS_CANDIDATE PENDING 1"
sqlx "UPDATE goal SET lifecycle_state='ARCHIVED' WHERE goal_id='g.test-only-0'"; dry_refuses "an unknown state" "GOAL_STATE_NOT_TERMINAL ARCHIVED 1"
sqlx "UPDATE goal SET lifecycle_state='COMPLETED' WHERE goal_id='g.test-only-0'"
sqlx "INSERT INTO goal_trace (correlation_id, at, kind) VALUES ('g_arb_old','a','arbitration')"; dry_refuses "an existing arbitration trace" GOAL_ARBITRATION_TRACE_PRESENT
sqlx "DELETE FROM goal_trace WHERE correlation_id='g_arb_old'"
cp "${APIREL}/app.py" "$S/app.bak"; sed -i 's/if _os.getenv("LILITH_OS_FOCUS_READ_ONLY") != "1":/if True:/' "${APIREL}/app.py"; touch -d '-1 min' "${APIREL}/app.py"
dry_refuses "Core API code that ignores the flag" FOCUS_GUARD_MISSING
cp "$S/app.bak" "${APIREL}/app.py"; touch -d '-1 min' "${APIREL}/app.py"
touch "${APIREL}/app.py"; sleep 2; dry_refuses "Core API code replaced after the process started" CORE_API_CODE_CHANGED_SINCE_START
touch -d '-1 min' "${APIREL}/app.py"
check "goal rows back to DEV's shape after the refusals" '[[ $(goalrows) == "$ROWS0" ]]'

# --- staging failure and automatic revert ---------------------------------------------------------------------------
run env F8_FAIL_AT=staging bash "${GVI}" install "$GP"; NQ=$((NQ + 1))
check "staging failure keeps the partial release under a new name, changes nothing else" '[[ $RC -ne 0 && $OUT == *"partial release kept"* && $(state) == "$BASELINE" && ! -e ${GVREL} && $(gquarantined) -eq '"$NQ"' ]]'
for at in after_home after_switch; do
  run env F8_FAIL_AT=$at bash "${GVI}" install "$GP"
  check "injected failure at $at reverts to the e1 baseline" '[[ $RC -ne 0 && $OUT == *"INJECTED_FAILURE at '"$at"'"* && $OUT == *"GV1_REVERTED"* && $(state) == "$BASELINE" && $(verify) == "F8_VERIFY_FAIL GOAL_STORE_NOT_EMPTY" ]]'
  discard_gv
done

# --- install -----------------------------------------------------------------------------------------------------
run bash "${GVI}" install "$GP"
check "install succeeds (e1 before: GOAL_ONLY)" '[[ $RC -eq 0 && $OUT == *"GV1_INSTALLED current=f293e72-f9c2-cog1-wm1-g1-r1-w1-m1-p1-e1-gv1"* && $OUT == *"e1 before: GOAL_ONLY"* ]]'
check "  current is gv1 and verify --full passes on DEV's goal store" '[[ $(readlink "${BASE}/current") == releases/f293e72-f9c2-cog1-wm1-g1-r1-w1-m1-p1-e1-gv1 && $(verify) == "F8_VERIFY_PASS full f293e72-f9c2-cog1-wm1-g1-r1-w1-m1-p1-e1-gv1" ]]'
check "  HERMES_HOME byte-identical (router, modules, config, jobs)" '[[ $(homestate) == "$HOME0" ]]'
check "  goal and trace rows unchanged; no arbitration trace written" '[[ $(goalrows) == "$ROWS0" ]]'
check "  gv1 verifier is the gv1 template with the host token; only bin/verify_release.py and RELEASE_ID differ from e1" '[[ $(sha256sum < "${GVREL}/bin/verify_release.py") == $(render "${GV}/templates/bin/verify_release.py.tmpl" | sha256sum) && -n $(tree_of "${GVREL}") && $(diff <(sort -k2 "${E1REL}/RELEASE.sha256") <(sort -k2 "${GVREL}/RELEASE.sha256") | grep -c "^>") -eq 2 ]]'
check "  e1 and p1 releases untouched" '[[ $(tree_of "${E1REL}") == "$E1_TREE" && $(tree_of "${OLD}") == "$P1_TREE" ]]'
run bash "${GVI}" install "$GP"; check "second install refuses" '[[ $RC -ne 0 && $OUT == *"current is not f293e72-f9c2-cog1-wm1-g1-r1-w1-m1-p1-e1"* ]]'

# --- restart verification (what ExecStartPre runs) -----------------------------------------------------------------
check "restart: pre-start passes" '[[ $(prestart) == "F8_VERIFY_PASS pre-start f293e72-f9c2-cog1-wm1-g1-r1-w1-m1-p1-e1-gv1" ]]'
api_start ""; check "restart: Core API restarted without the flag refuses" '[[ $(prestart) == "F8_VERIFY_FAIL FOCUS_READ_ONLY_NOT_IN_EFFECT" && $(goalrows) == "$ROWS0" ]]'
api_stop; check "restart: Core API down refuses" '[[ $(prestart) == "F8_VERIFY_FAIL CORE_API_NOT_RUNNING inactive" ]]'
api_start 1
sqlx "UPDATE goal SET lifecycle_state='PENDING' WHERE goal_id='g.test-only-0'"
check "restart: a reopened (PENDING) goal refuses, with no focus read" '[[ $(prestart) == "F8_VERIFY_FAIL GOAL_FOCUS_CANDIDATE PENDING 1" && $(goalrows) != *", 1)" ]]'
sqlx "UPDATE goal SET lifecycle_state='COMPLETED' WHERE goal_id='g.test-only-0'"
cp "${LR}/router.yaml" "$S/router.bak"; chmod u+w "${LR}/router.yaml"; echo "# TEST_ONLY" >> "${LR}/router.yaml"
check "restart: a changed pinned file refuses (release integrity)" '[[ $(prestart) == *"HASH_MISMATCH"*"router.yaml"* ]]'
cp "$S/router.bak" "${LR}/router.yaml"; chmod 0640 "${LR}/router.yaml"
check "restart: pre-start passes again" '[[ $(prestart) == "F8_VERIFY_PASS pre-start f293e72-f9c2-cog1-wm1-g1-r1-w1-m1-p1-e1-gv1" && $(goalrows) == "$ROWS0" ]]'

# --- revert failures and resumption -------------------------------------------------------------------------------
for at in revert_before_switch revert_after_switch; do
  run env F8_FAIL_AT=$at bash "${GVI}" revert "$GP"
  check "revert failing at $at reports GV1_REVERT_FAIL" '[[ $RC -ne 0 && $OUT == *"INJECTED_FAILURE at '"$at"'"* && $OUT == *GV1_REVERT_FAIL* ]]'
  run bash "${GVI}" revert "$GP"
  check "  re-running revert completes to the e1 baseline" '[[ $RC -eq 0 && $OUT == *"GV1_REVERTED current=f293e72-f9c2-cog1-wm1-g1-r1-w1-m1-p1-e1"* && $(state) == "$BASELINE" && $(verify) == "F8_VERIFY_FAIL GOAL_STORE_NOT_EMPTY" ]]'
  discard_gv
  run bash "${GVI}" install "$GP"; [[ $RC -eq 0 ]] || fail "  re-install after $at"
done
run env SIM_GW="failed failed 0" bash "${GVI}" revert "$GP"
check "revert succeeds with the gateway in failed/failed; e1 back exactly (GOAL_ONLY, as on DEV today)" '[[ $RC -eq 0 && $OUT == *"e1 verifier: GOAL_ONLY"* && $(state) == "$BASELINE" && $(homestate) == "$HOME0" && $(goalrows) == "$ROWS0" ]]'
check "  gv1 release kept for inspection" '[[ -d ${GVREL} ]]'

echo "SIM_RESULT $([[ ${FAILS} -eq 0 ]] && echo PASS || echo "FAIL (${FAILS})")"
exit "${FAILS}"
