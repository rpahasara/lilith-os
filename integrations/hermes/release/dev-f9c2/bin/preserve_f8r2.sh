#!/usr/bin/env bash
# F8r4 upgrade step U-1 (root): PRESERVE the owner-accepted F8r2 installation before f8r4 is installed.
#   sudo bash bin/preserve_f8r2.sh
# 1. Proves the running install IS the accepted F8r2 (release id, RELEASE.sha256 digest, f8r2 verify --full).
# 2. Records an inventory of every F8r2 path (+ sha256 of every regular file, metadata of the rest), incl. runtime state.
# 3. Runs F8r2's OWN reviewed rollback (R-2: stop + MOVE everything to a root-only quarantine; never deletes).
# 4. Writes the preservation record used by restore_f8r2.sh. Touches nothing outside the F8r2 allowlist.
set -Eeuo pipefail
umask 077
[[ $(id -u) -eq 0 ]] || { echo "not root" >&2; exit 1; }
if [[ ${F8_SIM:-} == 1 ]]; then [[ $(hostname) != lilith-dev-01 ]] || exit 1; else [[ $(hostname) == lilith-dev-01 ]] || { echo "wrong host" >&2; exit 1; }; fi
die() { echo "F8_PRESERVE_FAIL $*" >&2; exit 1; }
F8R2_RELEASE_SHA=${F8R2_RELEASE_SHA:?set F8R2_RELEASE_SHA to the accepted F8r2 RELEASE.sha256 digest (Phase A record)}
REL=$(readlink -f /opt/hermes-gateway-dev/current) || die "no current release"
[[ $(basename "${REL}") == f293e72-f8r2 ]] || die "current release is $(basename "${REL}"), not f293e72-f8r2"
[[ $(sha256sum < "${REL}/RELEASE.sha256" | cut -c1-64) == "${F8R2_RELEASE_SHA}" ]] || die "RELEASE.sha256 digest differs from the accepted F8r2"
"${REL}/venv/bin/python" -I -B "${REL}/bin/verify_release.py" --full || die "f8r2 verify --full"
TS=$(date -u +%Y%m%dT%H%M%SZ); OUT=/var/backups/hermes-gateway-dev/f8r2-preserved-${TS}
install -d -o root -g root -m 0700 /var/backups/hermes-gateway-dev "${OUT}"
echo "gateway: $(systemctl show hermes-gateway-dev -p ActiveState,SubState,MainPID --value | paste -sd' ')" > "${OUT}/f8r2-runtime.txt"
bash "${REL}/bin/rollback.sh" stop > "${OUT}/f8r2-R1.log" 2>&1 || die "f8r2 R-1"
# Inventory AFTER the stop: stopping checkpoints Hermes' SQLite WAL, so state.db is final only now.
# Inventory line (TAB-separated, path LAST so paths with spaces stay intact):
#   <type> TAB <uid:gid> TAB <mode> TAB <size|-> TAB <sha256|->  <path>
inv() { for p in "$@"; do [[ -e $p || -L $p ]] || continue
          find "$p" -xdev \( -type f -printf '%y\t%U:%G\t%m\t%s\t' -exec sha256sum {} \; \) \
                -o \( ! -type f -printf '%y\t%U:%G\t%m\t-\t-  %p\n' \) ; done; }
inv /opt/hermes-gateway-dev /etc/hermes-gateway-dev /etc/systemd/system/hermes-gateway-dev.service \
    /etc/systemd/system/hermes-gateway-dev-retention.service /etc/systemd/system/hermes-gateway-dev-retention.timer \
    /etc/systemd/journald@hermes-gateway-dev.conf /home/lilith/.hermes-dev 2>/dev/null \
  | LC_ALL=C sort -t$'\t' -k5 > "${OUT}/f8r2-inventory.txt"
for _ in $(seq 1 30); do [[ $(systemctl list-jobs --no-legend | wc -l) -eq 0 ]] && break; sleep 2; done
bash "${REL}/bin/rollback.sh" remove > "${OUT}/f8r2-R2.log" 2>&1 || die "f8r2 R-2"
Q=$(grep -o 'quarantine=.*' "${OUT}/f8r2-R2.log" | cut -d= -f2)
[[ -d ${Q} ]] || die "no quarantine recorded"
grep -q F8_ROLLBACK_HOLD "${OUT}/f8r2-R2.log" && die "F8r2 R-2 held its daemon-reload (another unit pending) - owner decision before continuing"
printf 'quarantine=%s\nrelease_sha=%s\n' "${Q}" "${F8R2_RELEASE_SHA}" > "${OUT}/record"
(cd "${OUT}" && sha256sum f8r2-inventory.txt f8r2-runtime.txt f8r2-R1.log f8r2-R2.log record > SHA256SUMS)
echo "F8R2_PRESERVED ${OUT} quarantine=${Q} files=$(grep -c $'^f\t' "${OUT}/f8r2-inventory.txt")"
