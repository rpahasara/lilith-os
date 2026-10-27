#!/usr/bin/env bash
# F8r3 G-5b (OWNER ACTION, interactive, root on lilith-dev-01): install the DEV-only Groq project API key for the
# provider gate. The key is typed (not echoed), written once to a root-only file and never printed, logged or copied.
#   sudo bash bin/provision_provider_key.sh
# Pre-requisites (owner, Groq console): a dedicated DEV project, a project-scoped key, ZDR enabled in Data Controls,
# project rate limits set, spend limit set (paid plan) or free tier confirmed. Revocation is done in the Groq console.
set -Eeuo pipefail
umask 077
F=/etc/hermes-provider-gate-dev/credentials/groq-api-key
[[ $(id -u) -eq 0 ]] || { echo "not root" >&2; exit 1; }
[[ -d $(dirname "$F") && $(stat -c '%U %a' "$(dirname "$F")") == "root 700" ]] || { echo "credentials dir missing/unsafe" >&2; exit 1; }
[[ ! -e $F ]] || { echo "F8_KEY_REFUSED key already present (rotate = R-1, move it to quarantine, re-run)" >&2; exit 1; }
[[ -t 0 ]] || { echo "F8_KEY_REFUSED needs an interactive terminal (no pipes/stdin injection)" >&2; exit 1; }
read -r -s -p "Groq DEV project API key (input hidden): " KEY; echo
[[ ${KEY} =~ ^gsk_[A-Za-z0-9]{20,}$ ]] || { unset KEY; echo "F8_KEY_REFUSED unexpected key format" >&2; exit 1; }
tmp=$(mktemp "$(dirname "$F")/.key.XXXXXX"); printf '%s\n' "${KEY}" > "${tmp}"; unset KEY
chown root:root "${tmp}"; chmod 0600 "${tmp}"; mv -T "${tmp}" "$F"
echo "F8_KEY_PROVISIONED sha256_prefix=$(tr -d '\n' < "$F" | sha256sum | cut -c1-12) (restart the gate to load it)"
