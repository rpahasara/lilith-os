#!/usr/bin/env bash
# Gate G-5: create the NEW DEV-only console token on the host. The value is generated here, written once with
# root:lilith 0640 into HERMES_HOME/.env (read by the gateway and by the DEV Core API relay) and never printed,
# copied off the host or derived from any PROD value. Only its sha256 prefix is shown, for the record.
set -Eeuo pipefail
umask 077
ENV=/home/lilith/.hermes-dev/.env
[[ $(id -u) -eq 0 ]] || { echo "not root" >&2; exit 1; }
[[ ! -e ${ENV} ]] || { echo "F8_TOKEN_REFUSED ${ENV} exists (rotate = rollback R-2 first)" >&2; exit 1; }
tmp=$(mktemp /home/lilith/.hermes-dev/.env.XXXXXX)
{ echo "LILITH_OS_PORT=9901"; printf 'LILITH_OS_TOKEN=%s\n' "$(od -An -N32 -tx1 /dev/urandom | tr -d ' \n')"; } > "${tmp}"
chown root:lilith "${tmp}"; chmod 0640 "${tmp}"; mv -T "${tmp}" "${ENV}"
echo "F8_TOKEN_PROVISIONED sha256_prefix=$(grep '^LILITH_OS_TOKEN=' "${ENV}" | cut -d= -f2 | tr -d '\n' | sha256sum | cut -c1-12)"
