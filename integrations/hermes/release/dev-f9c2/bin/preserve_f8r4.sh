#!/usr/bin/env bash
# F9 upgrade step U-1 (root): PRESERVE the owner-accepted F8r4 Phase B installation before f9c is installed.
#   sudo F8R4_RELEASE_SHA=<accepted f8r4 RELEASE.sha256 digest> bash bin/preserve_f8r4.sh
# The F8r4-upgrade pattern (preserve_f8r2.sh), extended to the F8r4 provider gate:
# 1. Proves the running install IS the accepted F8r4 (release id, RELEASE.sha256 digest, f8r4 verify --full).
# 2. Records an inventory of every F8r4 path (+ sha256 of every regular file, metadata of the rest), incl. runtime
#    state and the provider gate (config, root-only credentials incl. the Groq key, ledger state).
# 3. Runs F8r4's OWN reviewed rollback (R-1 stop, R-2 MOVE everything to a root-only quarantine; never deletes).
#    The Groq key stays in that root-only quarantine: f9c does not carry it over (no provider call is possible until
#    the owner provisions a key again at G-5b; restore_f8r4.sh moves the original back).
# 4. Writes the preservation record used by restore_f8r4.sh. Touches nothing outside the F8r4 allowlist.
set -Eeuo pipefail
umask 077
[[ $(id -u) -eq 0 ]] || { echo "not root" >&2; exit 1; }
if [[ ${F8_SIM:-} == 1 ]]; then [[ $(hostname) != lilith-dev-01 ]] || exit 1; else [[ $(hostname) == lilith-dev-01 ]] || { echo "wrong host" >&2; exit 1; }; fi
die() { echo "F9_PRESERVE_FAIL $*" >&2; exit 1; }
F8R4_RELEASE_SHA=${F8R4_RELEASE_SHA:?set F8R4_RELEASE_SHA to the accepted F8r4 RELEASE.sha256 digest (Phase B record)}
REL=$(readlink -f /opt/hermes-gateway-dev/current) || die "no current release"
[[ $(basename "${REL}") == f293e72-f8r4 ]] || die "current release is $(basename "${REL}"), not f293e72-f8r4"
[[ $(sha256sum < "${REL}/RELEASE.sha256" | cut -c1-64) == "${F8R4_RELEASE_SHA}" ]] || die "RELEASE.sha256 digest differs from the accepted F8r4"
"${REL}/venv/bin/python" -I -B "${REL}/bin/verify_release.py" --full || die "f8r4 verify --full"
[[ ! -e /etc/hermes-forget && ! -e /var/lib/hermes-forget/in-progress ]] || die "F9-C state present on an F8r4 install"
TS=$(date -u +%Y%m%dT%H%M%SZ); OUT=/var/backups/hermes-gateway-dev/f8r4-preserved-${TS}
install -d -o root -g root -m 0700 /var/backups/hermes-gateway-dev "${OUT}"
{ echo "gateway: $(systemctl show hermes-gateway-dev -p ActiveState,SubState,MainPID --value | paste -sd' ')"
  echo "gate: $(systemctl show hermes-provider-gate-dev -p ActiveState,SubState,MainPID --value | paste -sd' ')"; } > "${OUT}/f8r4-runtime.txt"
bash "${REL}/bin/rollback.sh" stop > "${OUT}/f8r4-R1.log" 2>&1 || die "f8r4 R-1"
# Inventory AFTER the stop (Hermes checkpoints its SQLite WAL on stop). TAB-separated, path LAST:
#   <type> TAB <uid:gid> TAB <mode> TAB <size|-> TAB <sha256|->  <path>
inv() { for p in "$@"; do [[ -e $p || -L $p ]] || continue
          find "$p" -xdev \( -type f -printf '%y\t%U:%G\t%m\t%s\t' -exec sha256sum {} \; \) \
                -o \( ! -type f -printf '%y\t%U:%G\t%m\t-\t-  %p\n' \) ; done; }
SD=/etc/systemd/system
inv /opt/hermes-gateway-dev /etc/hermes-gateway-dev ${SD}/hermes-gateway-dev.service ${SD}/hermes-gateway-dev-retention.service \
    ${SD}/hermes-gateway-dev-retention.timer ${SD}/hermes-provider-gate-dev.service /etc/systemd/journald@hermes-gateway-dev.conf \
    /etc/hermes-provider-gate-dev /var/lib/hermes-provider-gate-dev /var/lib/private/hermes-provider-gate-dev \
    /home/lilith/.hermes-dev 2>/dev/null | LC_ALL=C sort -t$'\t' -k5 > "${OUT}/f8r4-inventory.txt"
for _ in $(seq 1 30); do [[ $(systemctl list-jobs --no-legend | wc -l) -eq 0 ]] && break; sleep 2; done
bash "${REL}/bin/rollback.sh" remove > "${OUT}/f8r4-R2.log" 2>&1 || die "f8r4 R-2 (see ${OUT}/f8r4-R2.log)"
Q=$(grep -o 'quarantine=.*' "${OUT}/f8r4-R2.log" | cut -d= -f2)
[[ -d ${Q} ]] || die "no quarantine recorded"
grep -q F8_ROLLBACK_HOLD "${OUT}/f8r4-R2.log" && die "F8r4 R-2 held its daemon-reload (another unit pending) - owner decision before continuing"
printf 'quarantine=%s\nrelease_sha=%s\npreserved_at=%s\n' "${Q}" "${F8R4_RELEASE_SHA}" "${TS}" > "${OUT}/record"
(cd "${OUT}" && sha256sum f8r4-inventory.txt f8r4-runtime.txt f8r4-R1.log f8r4-R2.log record > SHA256SUMS)
echo "F8R4_PRESERVED ${OUT} quarantine=${Q} files=$(grep -c $'^f\t' "${OUT}/f8r4-inventory.txt")"
