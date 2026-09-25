# LILITH 15B2b-B1c effective sudo proof for the routine DEV deployer.
#
# Sourced (never executed) by the owner installer, the owner pre-merge gate,
# and the routine DEV workflow. Installed root:root 0644 at
# /usr/local/lib/lilith-dev-deploy/effective_sudo_proof.sh.
#
#   lilith_dev_effective_sudo_proof <posix-user> owner   # as root: sudo -l -U
#   lilith_dev_effective_sudo_proof <posix-user> self    # as that user: sudo -l
#
# owner mode: an OS Login user that has never logged in is not yet resolvable.
# That is the only deferrable state; it creates nothing and grants nothing.
# self mode: the caller has logged in, so the identity must resolve and match.
# Either mode fails unless the effective rules are exactly the fixed helper.

LILITH_DEV_EXPECTED_SUDO='(root) NOPASSWD: /usr/local/sbin/lilith-dev-deploy deploy *, /usr/local/sbin/lilith-dev-deploy status'

lilith_dev_sudo_rules() {
  sed -n '/may run the following commands/,$p' | tail -n +2 | sed -e 's/^[[:space:]]*//' -e '/^$/d'
}

lilith_dev_effective_sudo_proof() {
  local user="$1" mode="$2" listing rules
  case "${mode}" in
    owner|self) ;;
    *) echo "SUDO_EFFECTIVE_PROOF=FAIL reason=INVALID_MODE"; return 1 ;;
  esac
  if ! getent passwd "${user}" > /dev/null; then
    if [ "${mode}" = owner ]; then
      echo "SUDO_EFFECTIVE_PROOF=DEFERRED reason=OSLOGIN_USER_NOT_MATERIALIZED user=${user}"
      return 0
    fi
    echo "SUDO_EFFECTIVE_PROOF=FAIL reason=IDENTITY_NOT_RESOLVABLE_AFTER_LOGIN user=${user}"
    return 1
  fi
  if [ "${mode}" = self ]; then
    if [ "$(id -un)" != "${user}" ]; then
      echo "SUDO_EFFECTIVE_PROOF=FAIL reason=UNEXPECTED_EFFECTIVE_USER user=$(id -un)"
      return 1
    fi
    listing="$(sudo -n -l 2>&1)" || true
  else
    listing="$(sudo -n -l -U "${user}" 2>&1)" || true
  fi
  rules="$(printf '%s\n' "${listing}" | lilith_dev_sudo_rules)"
  if [ "${rules}" = "${LILITH_DEV_EXPECTED_SUDO}" ]; then
    echo "SUDO_EFFECTIVE_PROOF=PASS user=${user} mode=${mode}"
    return 0
  fi
  echo "SUDO_EFFECTIVE_PROOF=FAIL reason=UNEXPECTED_SUDO_RULES user=${user} mode=${mode}"
  printf '%s\n' "${listing}"
  return 1
}
