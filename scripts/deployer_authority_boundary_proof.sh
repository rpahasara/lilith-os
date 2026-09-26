#!/bin/bash
# LILITH 15B2b-B1b-3d: routine DEV deployer authority-boundary proof (DR-5).
#
# Streamed by .github/workflows/deploy-dev.yml into `bash -s` on lilith-dev-01,
# running AS the routine deployer, before any deployment step. It is proof
# only: it grants, creates, changes, starts, and executes nothing. Its probes
# are read-only:
#
#   - `stat` and the shell `test -r/-w/-x` access checks (access(2));
#   - `sudo -n -l <command>` policy QUERIES, which ask sudo whether a command
#     would be permitted and never run it;
#   - `pkcheck` polkit authorization QUERIES, when pkcheck is installed.
#
# Rules:
#
#   PATH_ABSENT != ACCESS_DENIED. An absent object is DEFERRED_UNTIL_OBJECT_EXISTS
#   unless the ladder says it must exist, in which case its absence is a FAIL.
#
#   Ladder maturity is derived from the root-owned objects the owner ceremony
#   steps themselves create (docs/architecture/slice-15b2b-b1b3d-l2-custody-preparation.md).
#   The deployer cannot forge them: this proof shows, in the same run, that
#   it cannot write any parent directory they live in. No marker, flag, or
#   "accepted" state is introduced. Once any object of a ladder step exists,
#   every object of that step and of every earlier step must exist, be
#   root-owned with its exact mode, and be denied to the deployer.
#
# It proves the routine deployer boundary only. It says nothing about host
# root (DR-3: `ubuntu` is root-equivalent through sudo/lxd).
#
# The last line is `AUTHORITY_BOUNDARY_PROOF=PASS maturity=<step>` or
# `AUTHORITY_BOUNDARY_PROOF=FAIL ...`; the exit status is 0 only on PASS. The
# workflow also requires the exact PASS line, so a truncated or skipped run
# cannot pass.

set -u

readonly AB_DEPLOYER="sa_112096412008414111981"
readonly AB_SERVICE_USER="lilith-authority-dev"
readonly AB_BROKER_USER="lilith-memory-broker"
readonly AB_SYSTEMCTL="/usr/bin/systemctl"
readonly AB_TRUE="/usr/bin/true"
readonly AB_UNITS="lilith-authority-dev.service lilith-authority-dev.socket"
readonly AB_UNIT_VERBS="start stop restart reload try-restart reload-or-restart enable disable reenable mask unmask edit revert"
readonly AB_KEYGEN="/usr/local/sbin/lilith-authority-keygen-dev"
readonly AB_OPT="/opt/lilith-authority-dev"
readonly AB_CREDSTORE="/etc/credstore.encrypted"
readonly AB_HOST_KEY="/var/lib/systemd/credential.secret"
# Existing root-owned parents that govern creation of every ladder object.
readonly AB_PARENTS="/opt /etc /etc/systemd/system /etc/tmpfiles.d /usr/local/sbin /var/lib/systemd /etc/needrestart/conf.d /usr/local/lib/lilith-dev-deploy"
# Existing root-owned files whose integrity the maturity rule and this proof rely on.
readonly AB_ROOT_FILES="/etc/passwd /etc/group /usr/local/lib/lilith-dev-deploy/effective_sudo_proof.sh /etc/needrestart/conf.d/lilith-authority-sensitive.conf"
readonly AB_FORBIDDEN_GROUPS="root sudo adm lxd docker wheel google-sudoers systemd-journal lilith lilith-authority-dev lilith-recovery-witness lilith-memory-broker lilith-memory-ipc"
# Ladder, in order: step|path|kind|mode|extra denials. Account (L1a) is separate.
readonly AB_LADDER="
L1b.1|/opt/lilith-authority-dev|directory|755|
L1b.1|/opt/lilith-authority-dev/releases|directory|755|
L1b.2|/opt/lilith-authority-dev/current|symbolic link|777|
L1c.1|/etc/systemd/system/lilith-authority-dev.service|regular file|644|
L1c.1|/etc/systemd/system/lilith-authority-dev.socket|regular file|644|
L1c.1|/etc/tmpfiles.d/lilith-authority-dev.conf|regular file|644|
L1c.3|/usr/local/sbin/lilith-authority-keygen-dev|regular file|755|
L2a|/var/lib/systemd/credential.secret|regular file|400|-r
L2b.1|/etc/credstore.encrypted|directory|700|-r -x
"
readonly AB_STEPS="PRE_L1A L1a L1b.1 L1b.2 L1c.1 L1c.3 L2a L2b.1"
# Later authority state (L3 onward). Denied whenever present; not ladder-required here.
readonly AB_LATER="/etc/lilith-authority-dev /var/lib/lilith-authority-dev /run/lilith-authority-dev /run/credentials/lilith-authority-dev.service /var/lib/lilith-recovery-witness /run/lilith-recovery-witness"

AB_FAILED=0
AB_MATURITY="PRE_L1A"

ab_say() { printf '%s\n' "$*"; }
ab_fail() { ab_say "FAIL: $*"; AB_FAILED=1; }

# ------------------------------------------------------------------ probes ---
# Tests replace only these functions. Everything below them is decision logic.

ab_whoami() { id -un; }
ab_uid() { id -u; }
ab_groups() { id -nG; }
ab_stat() { stat -c '%F|%u|%g|%a' -- "$1" 2>/dev/null; }  # empty when absent or not statable
ab_readlink() { readlink -- "$1" 2>/dev/null; }
ab_can() { test "$1" "$2"; }                                 # access(2); creates nothing
ab_list_dir() { ls -A -- "$1" 2>/dev/null; }
ab_local_user() { grep -q "^$1:" /etc/passwd; }
ab_sudo_query() { sudo -n -l "$@" 2>&1; }                    # a policy query; never runs the command
ab_have_pkcheck() { command -v pkcheck >/dev/null 2>&1; }
ab_pkcheck() { pkcheck --action-id "$1" --process "$$" >/dev/null 2>&1; }

# --------------------------------------------------------------- decisions ---

ab_step_index() {
  local i=0 step
  for step in ${AB_STEPS}; do
    [ "${step}" = "$1" ] && { echo "${i}"; return 0; }
    i=$((i + 1))
  done
  echo 99
}

ab_raise() {  # ab_raise <step>: maturity becomes the later of the two
  if [ "$(ab_step_index "$1")" -gt "$(ab_step_index "${AB_MATURITY}")" ]; then
    AB_MATURITY="$1"
  fi
}

ab_deny() {  # ab_deny <op> <path>: the path must exist and the access must fail
  if [ -z "$(ab_stat "$2")" ]; then
    ab_fail "DENIAL_VACUOUS_PATH_ABSENT $1 $2"
  elif ab_can "$1" "$2"; then
    ab_fail "ALLOWED(unexpected) test $1 $2"
  else
    ab_say "DENIED: test $1 $2"
  fi
}

ab_sudo_denied() {  # ab_sudo_denied <label> <sudo -l args...>: must be a conclusive refusal
  local label="$1" out rc
  shift
  out="$(ab_sudo_query "$@")"
  rc=$?
  if [ "${rc}" -eq 0 ]; then
    ab_fail "ALLOWED(unexpected) sudo ${label}"
    return
  fi
  case "${out}" in
    *"unknown user"*|*"command not found"*|*"unable to resolve"*|*"unknown group"*)
      ab_fail "SUDO_QUERY_INCONCLUSIVE ${label}" ;;
    *) ab_say "DENIED: sudo ${label}" ;;
  esac
}

ab_expect_root_object() {  # <path> <kind> <mode>
  local meta kind uid gid mode
  meta="$(ab_stat "$1")"
  if [ -z "${meta}" ]; then
    ab_fail "LADDER_OBJECT_MISSING $1"
    return 1
  fi
  IFS='|' read -r kind uid gid mode <<< "${meta}"
  if [ "${kind}" != "$2" ] || [ "${uid}" != 0 ] || [ "${gid}" != 0 ] || [ "${mode}" != "$3" ]; then
    ab_fail "LADDER_OBJECT_CONTRACT $1 observed=${meta} expected=$2|0|0|$3"
    return 1
  fi
  return 0
}

ab_check_identity() {
  local who uid group
  who="$(ab_whoami)"
  uid="$(ab_uid)"
  if [ "${who}" != "${AB_DEPLOYER}" ] || [ "${uid}" = 0 ]; then
    ab_fail "UNEXPECTED_EFFECTIVE_USER user=${who} uid=${uid}"
  fi
  for group in $(ab_groups); do
    case " ${AB_FORBIDDEN_GROUPS} " in
      *" ${group} "*) ab_fail "PRIVILEGED_OR_AUTHORITY_GROUP ${group}" ;;
    esac
  done
}

ab_check_parents() {
  local path
  for path in ${AB_PARENTS}; do
    if ab_stat "${path}" | grep -q '^directory|0|0|'; then
      ab_deny -w "${path}"
    else
      ab_fail "PARENT_NOT_ROOT_DIRECTORY ${path}"
    fi
  done
  for path in ${AB_ROOT_FILES}; do
    if ab_stat "${path}" | grep -q '^regular file|0|0|'; then
      ab_deny -w "${path}"
    else
      ab_fail "ROOT_FILE_NOT_ROOT_OWNED ${path}"
    fi
  done
}

ab_check_sudo_as() {
  if ab_local_user "${AB_BROKER_USER}"; then
    ab_sudo_denied "-u ${AB_BROKER_USER} ${AB_TRUE}" -u "${AB_BROKER_USER}" "${AB_TRUE}"
  else
    ab_fail "NON_VACUOUS_SUDO_AS_PROXY_MISSING ${AB_BROKER_USER}"
  fi
  if ab_local_user "${AB_SERVICE_USER}"; then
    ab_raise L1a
    ab_sudo_denied "-u ${AB_SERVICE_USER} ${AB_TRUE}" -u "${AB_SERVICE_USER}" "${AB_TRUE}"
  else
    ab_say "DEFERRED_UNTIL_OBJECT_EXISTS: sudo -u ${AB_SERVICE_USER} (proxy: ${AB_BROKER_USER})"
  fi
}

ab_check_service_control() {
  local unit verb action
  if ! ab_stat "${AB_SYSTEMCTL}" | grep -q '^regular file|0|0|'; then
    ab_fail "SYSTEMCTL_NOT_ROOT_OWNED ${AB_SYSTEMCTL}"
    return
  fi
  ab_sudo_denied "${AB_SYSTEMCTL} daemon-reload" "${AB_SYSTEMCTL}" daemon-reload
  for unit in ${AB_UNITS}; do
    for verb in ${AB_UNIT_VERBS}; do
      ab_sudo_denied "${AB_SYSTEMCTL} ${verb} ${unit}" "${AB_SYSTEMCTL}" "${verb}" "${unit}"
    done
  done
  if ab_have_pkcheck; then
    for action in org.freedesktop.systemd1.manage-units org.freedesktop.systemd1.manage-unit-files \
        org.freedesktop.systemd1.reload-daemon; do
      if ab_pkcheck "${action}"; then
        ab_fail "ALLOWED(unexpected) polkit ${action}"
      else
        ab_say "DENIED: polkit ${action}"
      fi
    done
  else
    ab_say "NOT_PROVEN: polkit unit control (pkcheck unavailable; the effective-sudo proof still applies)"
  fi
}

ab_ladder_maturity() {
  local step path kind mode denies
  while IFS='|' read -r step path kind mode denies; do
    [ -n "${step}" ] || continue
    if [ -n "$(ab_stat "${path}")" ]; then
      ab_raise "${step}"
    fi
  done <<< "${AB_LADDER}"
}

ab_check_ladder() {
  local step path kind mode denies op target entry max
  max="$(ab_step_index "${AB_MATURITY}")"
  if [ "${max}" -ge "$(ab_step_index L1b.1)" ] && ! ab_local_user "${AB_SERVICE_USER}"; then
    ab_fail "LADDER_OBJECT_MISSING account ${AB_SERVICE_USER}"
  fi
  while IFS='|' read -r step path kind mode denies; do
    [ -n "${step}" ] || continue
    if [ "$(ab_step_index "${step}")" -gt "${max}" ]; then
      ab_say "DEFERRED_UNTIL_OBJECT_EXISTS: ${path} (${step})"
      continue
    fi
    ab_expect_root_object "${path}" "${kind}" "${mode}" || continue
    if [ "${kind}" = "symbolic link" ]; then
      target="$(ab_readlink "${path}")"
      if [[ ! "${target}" =~ ^releases/[0-9a-f]{40}$ ]]; then
        ab_fail "SELECTOR_TARGET ${path} target=${target}"
      fi
      continue  # the link itself has no meaningful write bit; its parent and target are checked
    fi
    ab_deny -w "${path}"
    for op in ${denies}; do
      ab_deny "${op}" "${path}"
    done
  done <<< "${AB_LADDER}"
  if [ "${max}" -ge "$(ab_step_index L1b.1)" ]; then
    for entry in $(ab_list_dir "${AB_OPT}/releases"); do
      if [[ "${entry}" =~ ^[0-9a-f]{40}$ ]] && ab_expect_root_object "${AB_OPT}/releases/${entry}" directory 755; then
        ab_deny -w "${AB_OPT}/releases/${entry}"
      else
        ab_fail "UNEXPECTED_RELEASE_ENTRY ${entry}"
      fi
    done
  fi
  if [ "${max}" -ge "$(ab_step_index L1b.2)" ]; then
    target="$(ab_readlink "${AB_OPT}/current")"
    if [ -n "${target}" ] && ab_expect_root_object "${AB_OPT}/${target}" directory 755; then
      ab_deny -w "${AB_OPT}/${target}"
    fi
  fi
  if [ "${max}" -ge "$(ab_step_index L1c.3)" ]; then
    ab_sudo_denied "${AB_KEYGEN} actor" "${AB_KEYGEN}" actor
    ab_sudo_denied "${AB_KEYGEN}" "${AB_KEYGEN}"
  else
    ab_say "DEFERRED_UNTIL_OBJECT_EXISTS: sudo ${AB_KEYGEN} (the effective-sudo proof still applies)"
  fi
  if [ "${max}" -ge "$(ab_step_index L2b.1)" ]; then
    ab_say "UNOBSERVABLE_BY_DESIGN: ${AB_CREDSTORE}/lilith-authority-dev.owner-actor.cred (parent is not traversable by the deployer; covered by the parent -x/-r denial)"
  else
    ab_say "DEFERRED_UNTIL_OBJECT_EXISTS: ${AB_CREDSTORE}/lilith-authority-dev.owner-actor.cred (L2b.2)"
  fi
}

ab_check_later_state() {
  local path
  for path in ${AB_LATER}; do
    if [ -n "$(ab_stat "${path}")" ]; then
      ab_deny -w "${path}"
      case "${path}" in
        /var/lib/*|/run/*) ab_deny -r "${path}" ;;
      esac
    else
      ab_say "DEFERRED_UNTIL_OBJECT_EXISTS: ${path} (later step)"
    fi
  done
}

ab_main() {
  AB_FAILED=0
  AB_MATURITY="PRE_L1A"
  ab_check_identity
  ab_check_parents
  ab_check_sudo_as
  ab_check_service_control
  ab_ladder_maturity
  ab_check_ladder
  ab_check_later_state
  if [ "${AB_FAILED}" -eq 0 ]; then
    ab_say "AUTHORITY_BOUNDARY_PROOF=PASS maturity=${AB_MATURITY}"
    return 0
  fi
  ab_say "AUTHORITY_BOUNDARY_PROOF=FAIL maturity=${AB_MATURITY}"
  return 1
}

# Sourcing with AB_LIBRARY_ONLY=1 only defines functions (tests). It cannot
# pass the gate: the workflow requires the exact PASS line printed by ab_main.
if [ "${AB_LIBRARY_ONLY:-}" != 1 ]; then
  ab_main
  exit $?
fi
