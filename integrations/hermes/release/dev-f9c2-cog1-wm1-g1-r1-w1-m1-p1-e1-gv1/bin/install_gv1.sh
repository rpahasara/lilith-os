#!/usr/bin/env bash
# e1-gv1 DEV install and revert (lilith-dev-01). Root only. Run from a root-owned 0700 payload directory holding exactly
# the four PAYLOAD files below (from Git: this release's verifier template and RELEASE_ID, the e1 verifier template and
# the e1 router). Two phases, so the gateway keeps serving until the final switch:
#   sudo bash install_gv1.sh stage  <payload-dir>   gateway may RUN. Build releases/<NEW_ID> beside e1 (only new files there),
#                                                    dry-run its verifier against the live host. Nothing else changes.
#   sudo bash install_gv1.sh check  <payload-dir>   gateway may RUN. Re-check the staged release's integrity and re-run the
#                                                    dry run, immediately before stopping the gateway. Changes nothing.
#   sudo bash install_gv1.sh switch <payload-dir>   gateway STOPPED. Same checks again, then switch current, re-pin,
#                                                    verify --full. The gateway is NOT started here.
#   sudo bash install_gv1.sh install <payload-dir>  gateway STOPPED. stage + switch in one run (as install_e1.sh).
#   sudo bash install_gv1.sh revert <payload-dir>   gateway STOPPED. Switch current back to e1, re-pin, check e1 is back.
# Adapted from install_e1.sh: same host, payload, gateway, FORGET-lock, staging, revert and simulation guards.
# gv1 changes ONLY bin/verify_release.py (and RELEASE_ID): HERMES_HOME, router.yaml, every lilith_router module, units,
# sudoers, the Core API, its DB, the goal store, broker, authority, witness, Privacy, memory, credentials and the provider
# budget are untouched, and nothing is deleted.
# e1 today refuses with exactly "GOAL_STORE_NOT_EMPTY" (terminal TEST_ONLY goals from the 2026-11-09 P4-4 test); that one
# refusal, and only that one, is accepted as the e1 baseline. Consequence: once stopped, the gateway cannot start on e1
# again, so a revert restores e1 but NOT service (see the release README's recovery runbook).
# Failure: GV1_INSTALL_FAIL. A failed revert (GV1_REVERT_FAIL) can be re-run: every revert step is idempotent.
set -Eeuo pipefail
umask 022
MODE=${1:?usage: install_gv1.sh stage|check|switch|install|revert <payload-dir>}
PAY=$(readlink -f "${2:?payload dir}")
BASE=/opt/hermes-gateway-dev
OLD_ID=f293e72-f9c2-cog1-wm1-g1-r1-w1-m1-p1-e1
NEW_ID=f293e72-f9c2-cog1-wm1-g1-r1-w1-m1-p1-e1-gv1
OLD=${BASE}/releases/${OLD_ID}
NEW=${BASE}/releases/${NEW_ID}
HH=/home/lilith/.hermes-dev
LR=${HH}/lilith_router
CRITICAL=/etc/hermes-gateway-dev/critical.sha256
FORGET=/var/lib/hermes-forget
FORGET_LOCK=${FORGET}/state/.lock
DEV_MACHINE_ID=ae929170e6fa4c8ab9cc7b9547238d9d
# Payload pins (reviewed bytes in Git at the merge of this installer).
declare -A PAYLOAD=(
  [verify_release.gv1.py.tmpl]=ba814bdcacdc0882c57d9f84feff587ade40a459822a95291dda1f90e1591115   # gv1 verifier
  [verify_release.e1.py.tmpl]=f1086cacc440d84850b30b033b23120e41f34919d2761ddb2e867761eb3b65d5   # installed e1 verifier
  [router.e1.yaml]=be8c08d1c5e88e03306d33869239823bd61d367740a160a8133fd9353943e6f4   # installed e1 router (unchanged by gv1)
  [RELEASE_ID]=c33363446fcdcb8776c1db052751f96505e592d7066ce201652a46e1eac02618   # release identity
)
E1_ADAPTER_SHA=f1ee561dec06a7cadd282bc2e9e1315e39dd78f9be163d373237f941d84d55b2       # installed e1 world_context.py
E1_ETHICS_SHA=d6a1c20b45557169a4fefa7b5d81907da0e0ae12519f8c63724900ac8ce47dbd        # installed e1 ethics.py
PROD_WORKING_MEMORY_SHA=46b8187e3f6f2ac72c920de9dab12fd9c2841551f6c2aa7c20fd91941e3f0104
PHASE=preconditions        # preconditions | staging | home | reverting | done
STAGE=
die() { echo "GV1_INSTALL_FAIL $*" >&2; exit 1; }
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

home_is_e1() {   # gv1 changes nothing in HERMES_HOME: it must be exactly e1's
  [[ $(sha "${LR}/router.yaml") == "${PAYLOAD[router.e1.yaml]}" ]] || die "installed router.yaml is not the e1 one"
  [[ $(sha "${LR}/world_context.py") == "${E1_ADAPTER_SHA}" ]] || die "installed world_context is not the e1 adapter"
  [[ $(sha "${LR}/ethics.py") == "${E1_ETHICS_SHA}" ]] || die "installed ethics is not the e1 one"
  [[ $(sha "${LR}/_prod_world_context.py") == "${PROD_WORKING_MEMORY_SHA}" ]] || die "installed PROD module differs"
}

preconditions() {   # every mode; the gateway-state rule is the caller's
  [[ $(id -u) -eq 0 ]] || die "not root"
  if [[ ${SIM} != 1 ]]; then [[ $(hostname) == lilith-dev-01 ]] || die "wrong host $(hostname)"; fi
  payload_ok
  [[ -d ${OLD} && ! -L ${OLD} ]] || die "${OLD_ID} release missing"
  home_is_e1
  take_forget_lock
  no_forget_pending
}

e1_verdict() {   # the e1 verifier on the live host: PASS | GOAL_ONLY (exactly the one known refusal) | OTHER
  local out
  out=$("${OLD}/venv/bin/python" -I -B "${OLD}/bin/verify_release.py" --full 2>&1) || true
  if [[ ${out} == "F8_VERIFY_PASS full ${OLD_ID}" ]]; then echo PASS
  elif [[ ${out} == "F8_VERIFY_FAIL GOAL_STORE_NOT_EMPTY" ]]; then echo GOAL_ONLY
  else echo OTHER; fi
}

e1_baseline() {   # current is e1, pinned to e1, and e1 refuses for no reason other than the known one
  [[ $(readlink -f "${BASE}/current") == "${OLD}" ]] || die "current is not ${OLD_ID}"
  ! grep -q "  ${NEW#/}/" "${CRITICAL}" || die "the critical pins name ${NEW_ID}: finish or re-run the revert first"
  E1_BEFORE=$(e1_verdict)
  [[ ${E1_BEFORE} == PASS || ${E1_BEFORE} == GOAL_ONLY ]] || die "e1 verify --full refuses for another reason"
}

render_to() {   # $1 template, $2 output file, or "-" for the SHA-256 of the render only (nothing written)
  # The template with the token of the installed e1 verifier; the token never leaves the host.
  python3 -I - "${PAY}/verify_release.e1.py.tmpl" "${OLD}/bin/verify_release.py" "$1" "$2" <<'PY' || die "verifier render"
import hashlib, os, sys
PH = b"__LILITH_GATE_CLIENT_TOKEN__"
base_t, base_r, new_t = (open(p, "rb").read() for p in sys.argv[1:4])
out = sys.argv[4]
head, rest = base_t.split(PH, 1)
tail = rest.split(PH, 1)[0]
if not base_r.startswith(head):
    sys.exit("TEMPLATE_PREFIX")
token = base_r[len(head):base_r.index(tail, len(head))] if tail else base_r[len(head):]
if not token or PH in token or b"\n" in token or base_t.replace(PH, token) != base_r:
    sys.exit("E1_RENDER_MISMATCH")
rendered = new_t.replace(PH, token)
if out == "-":
    print(hashlib.sha256(rendered).hexdigest())
    sys.exit(0)
tmp = out + ".tmp"
with open(tmp, "wb") as fh:
    fh.write(rendered)
os.chmod(tmp, 0o644)
os.replace(tmp, out)
PY
}

staged_ok() {   # the staged release is exactly e1 + the two gv1 members, read-only, root-owned, manifest intact
  [[ -d ${NEW} && ! -L ${NEW} ]] || die "${NEW_ID} is not staged (run: install_gv1.sh stage)"
  [[ $(stat -c '%U %a' "${NEW}") == "root 555" ]] || die "staged release is not root 0555"
  [[ -z $(find "${NEW}" -mindepth 1 \( ! -user root -o -perm /0222 \) ! -type l -print -quit) ]] \
    || die "staged release has a non-root or writable file"
  (cd "${NEW}" && sha256sum -c --quiet --strict RELEASE.sha256 >/dev/null 2>&1) || die "staged release fails its RELEASE.sha256"
  [[ $(cd "${NEW}" && find . -name __pycache__ -prune -o -type f ! -name 'RELEASE.sha256*' -print | wc -l) \
     -eq $(wc -l < "${NEW}/RELEASE.sha256") ]] || die "staged release holds files outside its manifest"
  [[ $(sha "${NEW}/RELEASE_ID") == "${PAYLOAD[RELEASE_ID]}" ]] || die "staged RELEASE_ID differs"
  local d
  d=$(diff <(LC_ALL=C sort -k2 "${OLD}/RELEASE.sha256") <(LC_ALL=C sort -k2 "${NEW}/RELEASE.sha256") | grep '^[<>]' \
      | awk '{print $1, $3}' | LC_ALL=C sort | paste -sd' ') || true
  [[ ${d} == "< RELEASE_ID < bin/verify_release.py > RELEASE_ID > bin/verify_release.py" ]] \
    || die "staged release differs from e1 beyond RELEASE_ID and bin/verify_release.py (${d:-none})"
  local want
  want=$(render_to "${PAY}/verify_release.gv1.py.tmpl" -)
  [[ -n ${want} && ${want} == $(sha "${NEW}/bin/verify_release.py") ]] \
    || die "staged verifier is not the gv1 template with this host's token"
}

dry_run() {   # $1: the verifier to run. It judges the live host, still current=e1. One read-only focus read.
  local out
  out=$("${OLD}/venv/bin/python" -I -B "$1" --full 2>&1) || true
  if [[ ${out} != "F8_VERIFY_PASS full ${OLD_ID}" ]]; then
    printf '%s\n' "${out}" | sed 's/^/    /' >&2
    die "the gv1 verifier refuses this host (dry run); nothing shared changed"
  fi
}

verify_full() {   # the installed release's own gate: F8_VERIFY_PASS or nothing
  "${BASE}/current/venv/bin/python" -I -B "${BASE}/current/bin/verify_release.py" --full | tail -1 \
    | grep -qx "F8_VERIFY_PASS full $1"
}

switch_current() {
  ln -sfn "releases/$1" "${BASE}/current.new" && mv -Tf "${BASE}/current.new" "${BASE}/current"
}

stage() {   # builds NEW beside e1; the only writes are under releases/ (NEW, or a quarantined partial on failure)
  [[ ! -e ${NEW} && ! -e ${NEW}.new ]] || die "${NEW_ID} already staged"
  avail_mb=$(df -Pm "${BASE}" | awk 'NR==2{print $4}'); used_mb=$(du -sm "${OLD}" | cut -f1)
  (( avail_mb > used_mb + 512 )) || die "not enough space to stage ${NEW_ID}"
  step "stage ${NEW_ID} beside ${OLD_ID}; render the gv1 verifier on this host (token stays on the host)"
  PHASE=staging
  STAGE=${NEW}.new
  install -d -o root -g root -m 0700 "${STAGE}"
  cp -a "${OLD}/." "${STAGE}/"
  inject staging
  render_to "${PAY}/verify_release.gv1.py.tmpl" "${STAGE}/bin/verify_release.py"
  install -o root -g root -m 0644 "${PAY}/RELEASE_ID" "${STAGE}/RELEASE_ID"
  (cd "${STAGE}" && find . -name __pycache__ -prune -o -type f ! -name 'RELEASE.sha256*' -print | sed 's|^\./||' \
    | LC_ALL=C sort | xargs -r -d '\n' sha256sum) > "${STAGE}/RELEASE.sha256"
  chown -R root:root "${STAGE}"; chmod -R a-w "${STAGE}"; chmod 0555 "${STAGE}"
  inject staged
  step "dry run: the staged gv1 verifier judges the live host (read-only; one focus read)"
  dry_run "${STAGE}/bin/verify_release.py"
  mv -T "${STAGE}" "${NEW}"
  STAGE=
  PHASE=preconditions
  staged_ok
}

switch() {   # gateway stopped; NEW staged and checked
  no_forget_pending
  gateway_stopped
  step "switch current to ${NEW_ID}; re-pin"
  PHASE=home
  inject after_home
  switch_current "${NEW_ID}"
  inject after_switch
  bash "${NEW}/bin/pin_critical.sh" "${NEW}"
  verify_full "${NEW_ID}" || { echo "GV1_INSTALL_FAIL gv1 verify --full" >&2; exit 1; }
  home_is_e1
  gateway_stopped
  PHASE=done
  echo "GV1_INSTALLED current=${NEW_ID} (gateway not started; e1 before: ${E1_BEFORE}; HERMES_HOME unchanged)"
}

revert() {   # idempotent; safe to re-run after a partial revert
  PHASE=reverting
  step "revert to ${OLD_ID}"
  inject revert_before_switch
  switch_current "${OLD_ID}"
  inject revert_after_switch
  bash "${OLD}/bin/pin_critical.sh" "${OLD}"
  v=$(e1_verdict)
  [[ ${v} == PASS || ${v} == GOAL_ONLY ]] || { echo "GV1_REVERT_FAIL e1 verify --full after revert: ${v}" >&2; exit 1; }
  PHASE=done
  echo "GV1_REVERTED current=${OLD_ID} (e1 verifier: ${v}; with GOAL_ONLY the gateway cannot start, exactly as before gv1)"
}

on_exit() {
  local rc=$?
  [[ ${rc} -ne 0 ]] || return 0
  case ${PHASE} in
    staging)
      if [[ -n ${STAGE} && -e ${STAGE} ]]; then
        local kept
        kept=$(mktemp -d "${BASE}/releases/.gv1-failed-staging-$(date -u +%Y%m%dT%H%M%SZ).XXXXXX")  # new, empty
        mv -T "${STAGE}" "${kept}" && echo "GV1_INSTALL_FAIL staging failed; partial release kept at ${kept}; nothing else changed" >&2
      else
        echo "GV1_INSTALL_FAIL staging failed; nothing changed" >&2
      fi
      ;;
    home)
      echo "GV1_INSTALL_FAIL after changes: reverting" >&2
      ( trap - EXIT; revert ) || echo "GV1_REVERT_FAIL automatic revert incomplete: re-run 'install_gv1.sh revert'" >&2
      ;;
    reverting)
      echo "GV1_REVERT_FAIL revert incomplete: re-run 'install_gv1.sh revert' (every step is idempotent)" >&2
      ;;
  esac
  exit "${rc}"
}
trap on_exit EXIT
trap 'exit 1' ERR

case ${MODE} in
  stage)        # the gateway may keep running
    step "preconditions (gateway may run)"
    preconditions
    e1_baseline
    stage
    echo "GV1_STAGED ${NEW_ID} (dry run PASS; current still ${OLD_ID}; gateway untouched; e1 before: ${E1_BEFORE})"
    ;;
  check)        # the gateway may keep running; changes nothing
    step "preconditions (gateway may run)"
    preconditions
    e1_baseline
    staged_ok
    inject check_before_dry
    dry_run "${NEW}/bin/verify_release.py"
    echo "GV1_CHECK_PASS ${NEW_ID} staged and verified; dry run PASS; safe to stop the gateway and switch"
    ;;
  switch)
    step "preconditions (gateway stopped)"
    preconditions
    gateway_stopped
    e1_baseline
    staged_ok
    dry_run "${NEW}/bin/verify_release.py"
    switch
    ;;
  install)
    step "preconditions (gateway stopped)"
    preconditions
    gateway_stopped
    e1_baseline
    stage
    switch
    ;;
  revert)
    step "preconditions"
    preconditions
    gateway_stopped
    cur=$(readlink -f "${BASE}/current")
    [[ ${cur} == "${NEW}" || ${cur} == "${OLD}" ]] || die "current is neither ${NEW_ID} nor ${OLD_ID}"
    if [[ ${cur} == "${OLD}" ]] && ! grep -q "  ${NEW#/}/" "${CRITICAL}"; then
      # current is e1 AND the pins no longer name gv1 (a revert interrupted after the switch still has gv1 pins)
      v=$(e1_verdict)
      [[ ${v} == OTHER ]] || die "nothing to revert: ${OLD_ID} is current and pinned (e1 verifier: ${v})"
    fi
    revert
    ;;
  *) die "unknown mode ${MODE}" ;;
esac
