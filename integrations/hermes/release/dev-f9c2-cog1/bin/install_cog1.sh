#!/usr/bin/env bash
# f9c2-cog1 DEV install and revert (lilith-dev-01). Root only. Run from a root-owned 0700 payload directory that holds
# exactly the six PAYLOAD files below (from Git: RELEASE-DELTA.json sources, the f9c2 stub and the f9c2 template):
#   sudo bash install_cog1.sh install <payload-dir>   stage releases/f293e72-f9c2-cog1 beside f9c2, install the two
#                                                     lilith_router files, switch current, re-pin, verify --full
#   sudo bash install_cog1.sh revert  <payload-dir>   switch current back to f9c2, restore the stub, MOVE
#                                                     _prod_world_context.py to /var/backups, re-pin, verify --full
# The gateway must be stopped first and is NOT started here (separate gates). No unit, sudoers, user, group, Core API,
# broker, authority, witness, Privacy, memory or credential change; no daemon-reload; nothing is deleted. The
# provider-gate client token never leaves the host: the cog1 verifier is rendered from the installed f9c2 verifier,
# after proving the f9c2 template renders to exactly those installed bytes.
# The copied release keeps the f9c2 venv, whose interpreter and editable Hermes src resolve into releases/f293e72-f9c2
# (identical, verified bytes): f9c2 must stay in place while cog1 is current. It is also the revert target.
# Failure: COG1_INSTALL_FAIL (install refuses before any change on a precondition; after a change it reverts).
set -Eeuo pipefail
umask 022
MODE=${1:?usage: install_cog1.sh install|revert <payload-dir>}
PAY=$(readlink -f "${2:?payload dir}")
BASE=/opt/hermes-gateway-dev
OLD_ID=f293e72-f9c2
NEW_ID=f293e72-f9c2-cog1
OLD=${BASE}/releases/${OLD_ID}
NEW=${BASE}/releases/${NEW_ID}
HH=/home/lilith/.hermes-dev
LR=${HH}/lilith_router
BACKUP=/var/backups/hermes-gateway-dev
# Payload pins (reviewed bytes in Git at the merge of this installer).
declare -A PAYLOAD=(
  [world_context.py]=07a763e1dd3d81e883c415c9b051332785b52313a00048f0cb1da57effe4a8fc           # governed adapter
  [_prod_world_context.py]=46b8187e3f6f2ac72c920de9dab12fd9c2841551f6c2aa7c20fd91941e3f0104     # PROD Working Memory
  [world_context.f9c2-stub.py]=5c1fbf98ead049013aa79fdfb4e74dd3dd210ab0c3386f257ce0b4e334e6a3d5 # f9c2 import stub
  [verify_release.cog1.py.tmpl]=817f7cae2c4f78c5bdfb707893ef52802f621b6b2e62409f5969f4552b746840
  [verify_release.f9c2.py.tmpl]=865be1237ffe108322babdcca589c4bee426ef59813344e2706c34fe89ea649e
  [RELEASE_ID]=7c5467d4ff179e142a1353492ebbc370f8529de2e0247bcba13459e491cabb09
)
F9C2_VERIFY_SHA=b33c8971f335bd16e60b869d3b1e30b1828a616fec023db7b3bb607b878ca23e   # installed f9c2 bin/verify_release.py
die() { echo "COG1_INSTALL_FAIL $*" >&2; exit 1; }
step() { echo "--- $*"; }
sha() { sha256sum "$1" | cut -d' ' -f1; }
# Failure-injection hook for the offline simulation only (as install.sh; F8_SIM=1 is refused on lilith-dev-01).
inject() { if [[ ${F8_SIM:-} == 1 && ${F8_FAIL_AT:-} == "$1" ]]; then echo "INJECTED_FAILURE at $1" >&2; false; fi; }

preconditions() {   # $1 = release that current must point to
  [[ $(id -u) -eq 0 ]] || die "not root"
  if [[ ${F8_SIM:-} == 1 ]]; then [[ $(hostname) != lilith-dev-01 ]] || die "F8_SIM refused on lilith-dev-01"
  else [[ $(hostname) == lilith-dev-01 ]] || die "wrong host $(hostname)"; fi
  [[ $(stat -c '%U %a %F' "${PAY}") == "root 700 directory" ]] || die "payload dir must be root 0700"
  [[ $(find "${PAY}" -mindepth 1 | wc -l) -eq ${#PAYLOAD[@]} ]] || die "payload dir must hold exactly the payload files"
  local f
  for f in "${!PAYLOAD[@]}"; do
    [[ -f ${PAY}/$f && ! -L ${PAY}/$f ]] || die "payload lacks $f"
    [[ $(sha "${PAY}/$f") == "${PAYLOAD[$f]}" ]] || die "payload digest $f"
  done
  [[ $(readlink -f "${BASE}/current") == "${BASE}/releases/$1" ]] || die "current is not $1"
  [[ -d ${OLD} && ! -L ${OLD} ]] || die "${OLD_ID} release missing"
  [[ $(systemctl show hermes-gateway-dev -p ActiveState --value) != active ]] || die "gateway running (stop it first)"
  [[ ! -e /var/lib/hermes-forget/in-progress && -z $(ls -A /var/lib/hermes-forget/intent 2>/dev/null) ]] \
    || die "FORGET pending: install/revert after it completes"
}

verify_full() {   # the installed release's own gate: F8_VERIFY_PASS or nothing
  "${BASE}/current/venv/bin/python" -I -B "${BASE}/current/bin/verify_release.py" --full | tail -1 \
    | grep -qx "F8_VERIFY_PASS full $1"
}

put() {   # atomic root 0644 install of $1 as $2 (same directory)
  install -o root -g root -m 0644 "$1" "$2.cog1-new"
  mv -f "$2.cog1-new" "$2"
}

switch_current() {
  ln -sfn "releases/$1" "${BASE}/current.new" && mv -Tf "${BASE}/current.new" "${BASE}/current"
}

revert() {
  step "revert to ${OLD_ID}"
  local q
  q=${BACKUP}/cog1-revert-$(date -u +%Y%m%dT%H%M%SZ)
  install -d -o root -g root -m 0700 "${BACKUP}" "${q}"
  switch_current "${OLD_ID}"
  put "${PAY}/world_context.f9c2-stub.py" "${LR}/world_context.py"
  if [[ -e ${LR}/_prod_world_context.py ]]; then mv "${LR}/_prod_world_context.py" "${q}/"; fi
  bash "${OLD}/bin/pin_critical.sh" "${OLD}"
  verify_full "${OLD_ID}" || die "f9c2 verify --full after revert"
  echo "COG1_REVERTED current=${OLD_ID} moved=${q}"
}

case ${MODE} in
  install)
    step "preconditions"
    preconditions "${OLD_ID}"
    [[ ! -e ${NEW} && ! -e ${NEW}.new ]] || die "${NEW_ID} already staged"
    [[ $(sha "${LR}/world_context.py") == "${PAYLOAD[world_context.f9c2-stub.py]}" ]] || die "installed world_context is not the f9c2 stub"
    [[ ! -e ${LR}/_prod_world_context.py ]] || die "_prod_world_context.py already present"
    # The real-token digest cannot exist in the offline simulation; the render proof below still runs there.
    [[ ${F8_SIM:-} == 1 || $(sha "${OLD}/bin/verify_release.py") == "${F9C2_VERIFY_SHA}" ]] || die "installed f9c2 verifier digest"
    verify_full "${OLD_ID}" || die "f9c2 verify --full before install"
    avail_mb=$(df -Pm "${BASE}" | awk 'NR==2{print $4}'); used_mb=$(du -sm "${OLD}" | cut -f1)
    (( avail_mb > used_mb + 512 )) || die "not enough space to stage ${NEW_ID}"

    step "render the cog1 verifier on this host (token stays on the host)"
    install -d -o root -g root -m 0700 "${NEW}.new"
    cp -a "${OLD}/." "${NEW}.new/"
    python3 -I - "${PAY}/verify_release.f9c2.py.tmpl" "${OLD}/bin/verify_release.py" \
      "${PAY}/verify_release.cog1.py.tmpl" "${NEW}.new/bin/verify_release.py" <<'PY' || die "verifier render"
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
    sys.exit("F9C2_RENDER_MISMATCH")
tmp = out + ".tmp"
with open(tmp, "wb") as fh:
    fh.write(new_t.replace(PH, token))
os.chmod(tmp, 0o644)
os.replace(tmp, out)
PY
    install -o root -g root -m 0644 "${PAY}/RELEASE_ID" "${NEW}.new/RELEASE_ID"
    chmod u+w "${NEW}.new"
    (cd "${NEW}.new" && find . -name __pycache__ -prune -o -type f ! -name 'RELEASE.sha256*' -print | sed 's|^\./||' \
      | LC_ALL=C sort | xargs -r -d '\n' sha256sum) > "${NEW}.new/RELEASE.sha256.tmp"
    mv "${NEW}.new/RELEASE.sha256.tmp" "${NEW}.new/RELEASE.sha256"
    chown -R root:root "${NEW}.new"; chmod -R a-w "${NEW}.new"; chmod 0755 "${NEW}.new"
    mv -T "${NEW}.new" "${NEW}"
    chmod a-w "${NEW}"

    step "install the governed adapter and the PROD Working Memory; switch current"
    trap 'echo "COG1_INSTALL_FAIL step failed after changes: reverting" >&2; revert; exit 1' ERR
    put "${PAY}/_prod_world_context.py" "${LR}/_prod_world_context.py"
    put "${PAY}/world_context.py" "${LR}/world_context.py"
    inject after_home
    switch_current "${NEW_ID}"
    inject after_switch
    bash "${NEW}/bin/pin_critical.sh" "${NEW}"
    verify_full "${NEW_ID}" || { echo "COG1_INSTALL_FAIL cog1 verify --full" >&2; false; }
    trap - ERR
    echo "COG1_INSTALLED current=${NEW_ID} (gateway not started; every lane off)"
    ;;
  revert)
    preconditions "${NEW_ID}"
    revert
    ;;
  *) die "unknown mode ${MODE}" ;;
esac
