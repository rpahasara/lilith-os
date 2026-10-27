#!/usr/bin/env bash
# Gate G-1 (C-1): pre-install backup + baseline observation. Backs up ONLY the F8 target directory (HERMES_HOME, today an
# empty memories/). Core API databases are never opened or copied: observe_host.sh records their sha256 (raw read) and
# metadata so G-9 can prove they are unchanged. No disk snapshot (C-2). Nothing is stopped, restarted or edited.
# Output: /var/backups/hermes-gateway-dev/pre-<UTC>/ (root 0700).
set -Eeuo pipefail
umask 077
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TS=$(date -u +%Y%m%dT%H%M%SZ)
# A backup taken while an F8 install is present (the F8r2 -> f8r4 upgrade) is named upgrade-pre-*: F8r2's own
# accepted rollback compares HERMES_HOME with the latest pre-* backup, which must stay its memories-only G-1.
if [[ $(ls -A /home/lilith/.hermes-dev) == memories ]]; then OUT=/var/backups/hermes-gateway-dev/pre-${TS}
else OUT=/var/backups/hermes-gateway-dev/upgrade-pre-${TS}; fi
install -d -o root -g root -m 0700 /var/backups/hermes-gateway-dev "${OUT}"
tar --numeric-owner --xattrs --acls -C /home/lilith -cpf "${OUT}/hermes-dev-home.tar" .hermes-dev
find /home/lilith/.hermes-dev -printf '%M %u:%g %s %P\n' | LC_ALL=C sort -k4 > "${OUT}/hermes-dev-home.listing"
bash "${HERE}/observe_host.sh" "${OUT}/observation" >/dev/null
(cd "${OUT}" && sha256sum hermes-dev-home.tar hermes-dev-home.listing observation/* > SHA256SUMS)
echo "F8_BACKUP_DONE ${OUT}"
