#!/usr/bin/env bash
# f9c2-cog1-wm1-g1-m1-p1 DEV install and revert (lilith-dev-01). Root only. Run from a root-owned 0700 payload directory that
# holds exactly the nine PAYLOAD files below (from Git: this release, the m1 router and the m1 verifier template):
#   sudo bash install_p1.sh install <payload-dir>    stage releases/f293e72-f9c2-cog1-wm1-g1-r1-w1-m1-p1 beside m1, install the p1
#                                                    router.yaml (World Model, Goals, Reasoning, Workspace, Motivation and Planning shadow on lilith_os),
#                                                    switch current, re-pin, verify --full
#   sudo bash install_p1.sh revert  <payload-dir>    restore the m1 router.yaml (World Model, Goals, Reasoning, Workspace and Motivation shadow), switch
#                                                    current back to m1, re-pin, verify --full
# Adapted from install_m1.sh (same lock, gateway, staging, revert and simulation guards). The gateway must be fully
# stopped first and is NOT started here (separate gates). No unit, sudoers, user, group, Core API, broker, authority,
# witness, Privacy, memory, credential or provider-budget change; no daemon-reload; nothing is deleted.
# FORGET: the whole run holds the FORGET executor's own lock (/var/lib/hermes-forget/state/.lock), so no erasure can
# overlap the router.yaml replacement, the release switch or a revert; intents and the erasure marker are re-checked
# under the lock and again before the first change.
# The provider-gate client token never leaves the host: the p1 verifier is rendered from the installed m1
# verifier, after proving the m1 template renders to exactly those installed bytes.
# The copied release keeps the venv whose interpreter and editable Hermes src resolve into releases/f293e72-f9c2:
# f9c2, cog1, wm1, g1 and m1 must all stay in place while p1 is current. m1 is the revert target.
# Failure: P1_INSTALL_FAIL. Before the first HERMES_HOME change nothing is changed except that a partial staging
# directory is renamed to releases/.p1-failed-staging-<UTC>.<random> (kept, never deleted); after it, the install
# reverts. A failed revert (P1_REVERT_FAIL) can be re-run: every revert step is idempotent.
set -Eeuo pipefail
umask 022
MODE=${1:?usage: install_p1.sh install|revert <payload-dir>}
PAY=$(readlink -f "${2:?payload dir}")
BASE=/opt/hermes-gateway-dev
OLD_ID=f293e72-f9c2-cog1-wm1-g1-r1-w1-m1
NEW_ID=f293e72-f9c2-cog1-wm1-g1-r1-w1-m1-p1
OLD=${BASE}/releases/${OLD_ID}
NEW=${BASE}/releases/${NEW_ID}
HH=/home/lilith/.hermes-dev
LR=${HH}/lilith_router
FORGET=/var/lib/hermes-forget
FORGET_LOCK=${FORGET}/state/.lock
DEV_MACHINE_ID=ae929170e6fa4c8ab9cc7b9547238d9d
# Payload pins (reviewed bytes in Git at the merge of this installer).
declare -A PAYLOAD=(
  [router.p1.yaml]=666b5f2003c40bbfa53a82987cddfdb0eb4511b1f8457b5d0a0d0ac60f2c77cc       # World Model, Goals, Reasoning, Workspace, Motivation and Planning shadow
  [router.m1.yaml]=3ff4d3dc5f0dcfda11b79ca2e026e98b0be5e6460c4e936f2912e268cdd527ff       # installed m1: World Model, Goals, Reasoning, Workspace and Motivation shadow
  [verify_release.p1.py.tmpl]=2487b2b6217e7f1e557ced02915821399b86d223c26ae70400a9a44bd39374da
  [verify_release.m1.py.tmpl]=9d2e914b18bac139aa62a83fb5a09b944649b98c674a1b75f7f5d5c49fae599a
  [planning.p1.py]=4c74337d76fdd76947c21fb654b4463f6acd1a39db3670737427cf9fb0647e5b   # p1-member counts-only trace
  [planning.m1.py]=e74f7f7e9c59b7b19bb17eaa4868cf4365a2d3c4edacf7818e887a242703b852   # p1-member installed m1 module
  [world_context.p1.py]=a96d705f8801f6a9689ed0d8f54383bc6de7764c2d92d91ecce00d687d9128db   # p1-member Planning detector, read memo, private application number
  [world_context.m1.py]=848fdb7d309659bcc889c8b8284dbe5e5e23830bed0b70e9649f6eabe10340d1   # p1-member installed m1 adapter
  [RELEASE_ID]=e3d4a51ada6f17c4a969a57614cd4a04fcac02072b6e2db9886b9dc04687a97f
)
ADAPTER_SHA=848fdb7d309659bcc889c8b8284dbe5e5e23830bed0b70e9649f6eabe10340d1        # installed m1 adapter, the install base
PROD_WORKING_MEMORY_SHA=46b8187e3f6f2ac72c920de9dab12fd9c2841551f6c2aa7c20fd91941e3f0104
PHASE=preconditions        # preconditions | staging | home | reverting | done
STAGE=
die() { echo "P1_INSTALL_FAIL $*" >&2; exit 1; }
step() { echo "--- $*"; }
sha() { sha256sum "$1" | cut -d' ' -f1; }

# Offline simulation only. F8_SIM=1 is honoured only inside a disposable sandbox: not a lilith-* host, not the DEV
# machine-id, a private mount namespace, and /opt on an overlay. Anywhere else it is refused before anything runs.
SIM=0
if [[ -n ${F8_SIM:-} ]]; then
  [[ ${F8_SIM} == 1 ]] || die "F8_SIM must be 1 or unset"
  [[ $(hostname) != lilith-* ]] || die "F8_SIM refused on $(hostname)"
  [[ $(cat /etc/machine-id 2>/dev/null) != "${DEV_MACHINE_ID}" ]] || die "F8_SIM refused on the DEV machine"
  [[ $(readlink /proc/1/ns/mnt) != "$(readlink /proc/self/ns/mnt)" ]] || die "F8_SIM needs a private mount namespace"
  [[ $(stat -f -c %T /opt) == overlayfs ]] || die "F8_SIM needs /opt on an overlay"
  SIM=1
fi
inject() {   # sim only: F8_FAIL_AT fails at a named point; F8_PROBE_AT runs F8_PROBE_CMD there (race tests)
  [[ ${SIM} == 1 ]] || return 0
  if [[ ${F8_PROBE_AT:-} == "$1" ]]; then bash -c "${F8_PROBE_CMD:?}"; fi
  if [[ ${F8_FAIL_AT:-} == "$1" ]]; then echo "INJECTED_FAILURE at $1" >&2; return 1; fi
}

gateway_stopped() {   # fully stopped: loaded, inactive/dead or failed/failed, no main process. Anything else refuses.
  local s
  s=$(systemctl show hermes-gateway-dev -p LoadState -p ActiveState -p SubState -p MainPID 2>/dev/null \
      | LC_ALL=C sort | paste -sd' ') || s=
  [[ ${s} == "ActiveState=inactive LoadState=loaded MainPID=0 SubState=dead" \
     || ${s} == "ActiveState=failed LoadState=loaded MainPID=0 SubState=failed" ]] \
    || die "gateway not fully stopped (${s:-state unknown})"
}

no_forget_pending() {
  [[ ! -e ${FORGET}/in-progress ]] || die "FORGET pending: erasure marker present"
  [[ -z $(ls -A "${FORGET}/intent" 2>/dev/null) ]] || die "FORGET pending: intent present"
}

take_forget_lock() {   # the executor's own flock; held on fd 9 until this process exits
  [[ -d ${FORGET}/state && ! -L ${FORGET}/state && $(stat -c %U "${FORGET}/state") == root ]] || die "FORGET state dir missing or untrusted"
  [[ ! -L ${FORGET_LOCK} ]] || die "FORGET lock is a symlink"
  umask 077; exec 9>>"${FORGET_LOCK}"; umask 022   # the executor creates it 0600 too
  flock -w 30 9 || die "FORGET executor busy (lock held)"
}

payload_ok() {
  [[ $(stat -c '%U %a %F' "${PAY}") == "root 700 directory" ]] || die "payload dir must be root 0700"
  [[ $(find "${PAY}" -mindepth 1 | wc -l) -eq ${#PAYLOAD[@]} ]] || die "payload dir must hold exactly the payload files"
  local f
  for f in "${!PAYLOAD[@]}"; do
    [[ -f ${PAY}/$f && ! -L ${PAY}/$f ]] || die "payload lacks $f"
    [[ $(sha "${PAY}/$f") == "${PAYLOAD[$f]}" ]] || die "payload digest $f"
  done
}

preconditions() {
  [[ $(id -u) -eq 0 ]] || die "not root"
  if [[ ${SIM} != 1 ]]; then [[ $(hostname) == lilith-dev-01 ]] || die "wrong host $(hostname)"; fi
  payload_ok
  [[ -d ${OLD} && ! -L ${OLD} ]] || die "${OLD_ID} release missing"
  a=$(sha "${LR}/world_context.py")
  [[ ${a} == "${ADAPTER_SHA}" || ${a} == "${PAYLOAD[world_context.p1.py]}" ]] || die "installed world_context is neither the p1 nor the p1 adapter"
  [[ $(sha "${LR}/_prod_world_context.py") == "${PROD_WORKING_MEMORY_SHA}" ]] || die "installed PROD module differs"
  gateway_stopped
  take_forget_lock
  no_forget_pending
}

verify_full() {   # the installed release's own gate: F8_VERIFY_PASS or nothing
  "${BASE}/current/venv/bin/python" -I -B "${BASE}/current/bin/verify_release.py" --full | tail -1 \
    | grep -qx "F8_VERIFY_PASS full $1"
}

put_router() {   # atomic root:lilith 0640 install of $1 as router.yaml (as install.sh installs it)
  install -o root -g lilith -m 0640 "$1" "${LR}/router.yaml.p1-new"
  mv -f "${LR}/router.yaml.p1-new" "${LR}/router.yaml"
}



put_code() {   # p1-member atomic root 0644 install of $1 as lilith_router/$2, as install_cog1.sh installs code
  install -o root -g root -m 0644 "$1" "${LR}/$2.p1-new"   # p1-member
  mv -f "${LR}/$2.p1-new" "${LR}/$2"   # p1-member
}   # p1-member

switch_current() {
  ln -sfn "releases/$1" "${BASE}/current.new" && mv -Tf "${BASE}/current.new" "${BASE}/current"
}

revert() {   # idempotent; safe to re-run after a partial revert
  PHASE=reverting
  step "revert to ${OLD_ID}"
  put_router "${PAY}/router.m1.yaml"
  put_code "${PAY}/world_context.m1.py" world_context.py   # p1-member
  put_code "${PAY}/planning.m1.py" planning.py   # p1-member
  inject revert_after_router
  switch_current "${OLD_ID}"
  inject revert_after_switch
  bash "${OLD}/bin/pin_critical.sh" "${OLD}"
  verify_full "${OLD_ID}" || { echo "P1_REVERT_FAIL m1 verify --full after revert" >&2; exit 1; }
  PHASE=done
  echo "P1_REVERTED current=${OLD_ID} (World Model, Goals, Reasoning, Workspace and Motivation shadow)"
}

on_exit() {
  local rc=$?
  [[ ${rc} -ne 0 ]] || return 0
  case ${PHASE} in
    staging)
      if [[ -n ${STAGE} && -e ${STAGE} ]]; then
        local kept
        kept=$(mktemp -d "${BASE}/releases/.p1-failed-staging-$(date -u +%Y%m%dT%H%M%SZ).XXXXXX")  # new, empty
        mv -T "${STAGE}" "${kept}" && echo "P1_INSTALL_FAIL staging failed; partial release kept at ${kept}; nothing else changed" >&2
      else
        echo "P1_INSTALL_FAIL staging failed; nothing changed" >&2
      fi
      ;;
    home)
      echo "P1_INSTALL_FAIL after changes: reverting" >&2
      ( trap - EXIT; revert ) || echo "P1_REVERT_FAIL automatic revert incomplete: re-run 'install_p1.sh revert'" >&2
      ;;
    reverting)
      echo "P1_REVERT_FAIL revert incomplete: re-run 'install_p1.sh revert' (every step is idempotent)" >&2
      ;;
  esac
  exit "${rc}"
}
trap on_exit EXIT
trap 'exit 1' ERR

case ${MODE} in
  install)
    step "preconditions"
    preconditions
    [[ $(readlink -f "${BASE}/current") == "${OLD}" ]] || die "current is not ${OLD_ID}"
    [[ ! -e ${NEW} && ! -e ${NEW}.new ]] || die "${NEW_ID} already staged"
    [[ $(sha "${LR}/router.yaml") == "${PAYLOAD[router.m1.yaml]}" ]] || die "installed router.yaml is not the m1 one"
    [[ $(sha "${LR}/world_context.py") == "${ADAPTER_SHA}" ]] || die "installed world_context is not the m1 adapter"   # p1-member
    [[ $(sha "${LR}/planning.py") == "${PAYLOAD[planning.m1.py]}" ]] || die "installed planning is not the m1 one"   # p1-member
    verify_full "${OLD_ID}" || die "m1 verify --full before install"
    avail_mb=$(df -Pm "${BASE}" | awk 'NR==2{print $4}'); used_mb=$(du -sm "${OLD}" | cut -f1)
    (( avail_mb > used_mb + 512 )) || die "not enough space to stage ${NEW_ID}"

    step "stage ${NEW_ID} beside ${OLD_ID}; render the p1 verifier on this host (token stays on the host)"
    PHASE=staging
    STAGE=${NEW}.new
    install -d -o root -g root -m 0700 "${STAGE}"
    cp -a "${OLD}/." "${STAGE}/"
    inject staging
    python3 -I - "${PAY}/verify_release.m1.py.tmpl" "${OLD}/bin/verify_release.py" \
      "${PAY}/verify_release.p1.py.tmpl" "${STAGE}/bin/verify_release.py" <<'PY' || die "verifier render"
import os, sys
PH = b"__LILITH_GATE_CLIENT_TOKEN__"
base_t, base_r, new_t = (open(p, "rb").read() for p in sys.argv[1:4])
out = sys.argv[4]
head, rest = base_t.split(PH, 1)
tail = rest.split(PH, 1)[0]
if not base_r.startswith(head):
    sys.exit("TEMPLATE_PREFIX")
token = base_r[len(head):base_r.index(tail, len(head))] if tail else base_r[len(head):]
if not token or PH in token or b"\n" in token or base_t.replace(PH, token) != base_r:
    sys.exit("M1_RENDER_MISMATCH")
tmp = out + ".tmp"
with open(tmp, "wb") as fh:
    fh.write(new_t.replace(PH, token))
os.chmod(tmp, 0o644)
os.replace(tmp, out)
PY
    install -o root -g root -m 0644 "${PAY}/RELEASE_ID" "${STAGE}/RELEASE_ID"
    (cd "${STAGE}" && find . -name __pycache__ -prune -o -type f ! -name 'RELEASE.sha256*' -print | sed 's|^\./||' \
      | LC_ALL=C sort | xargs -r -d '\n' sha256sum) > "${STAGE}/RELEASE.sha256.tmp"
    mv "${STAGE}/RELEASE.sha256.tmp" "${STAGE}/RELEASE.sha256"
    chown -R root:root "${STAGE}"; chmod -R a-w "${STAGE}"; chmod 0555 "${STAGE}"
    inject staged
    # Last look before the first shared change: the lock keeps the executor out; a new intent or a started gateway
    # still stops the install here, with HERMES_HOME untouched.
    no_forget_pending
    gateway_stopped
    mv -T "${STAGE}" "${NEW}"
    STAGE=

    step "install the p1 router.yaml (World Model, Goals, Reasoning, Workspace, Motivation and Planning shadow on lilith_os); switch current"
    PHASE=home
    put_router "${PAY}/router.p1.yaml"
    put_code "${PAY}/world_context.p1.py" world_context.py   # p1-member
    put_code "${PAY}/planning.p1.py" planning.py   # p1-member
    inject after_home
    switch_current "${NEW_ID}"
    inject after_switch
    bash "${NEW}/bin/pin_critical.sh" "${NEW}"
    verify_full "${NEW_ID}" || { echo "P1_INSTALL_FAIL p1 verify --full" >&2; exit 1; }
    gateway_stopped
    PHASE=done
    echo "P1_INSTALLED current=${NEW_ID} (gateway not started; World Model, Goals, Reasoning, Workspace, Motivation and Planning shadow on lilith_os, every other lane off)"
    ;;
  revert)
    step "preconditions"
    preconditions
    cur=$(readlink -f "${BASE}/current")
    [[ ${cur} == "${NEW}" || ${cur} == "${OLD}" ]] || die "current is neither ${NEW_ID} nor ${OLD_ID}"
    if [[ ${cur} == "${OLD}" && $(sha "${LR}/router.yaml") == "${PAYLOAD[router.m1.yaml]}" ]] && verify_full "${OLD_ID}"; then
      die "nothing to revert: ${OLD_ID} is current and verifies"
    fi
    revert
    ;;
  *) die "unknown mode ${MODE}" ;;
esac
