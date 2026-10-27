#!/usr/bin/env bash
# F8 read-only host observation (root). Writes ONLY into the output directory given. It opens no database, reads no
# credential content (credentials and custody objects: metadata only), starts/stops/reloads nothing.
#   observe_host.sh <outdir>
# Sections (one file each, compared by compare_observations.sh):
#   services   state of every pre-existing DEV unit (PID, InvocationID, NRestarts, start stamp, NeedDaemonReload)
#   units      sha256 of their unit files + drop-ins
#   sockets    listening TCP/UDP (non-F8) + the DEV unix sockets' owner/mode
#   custody    metadata of every authority / witness / broker / custody / credstore / activation / deployer object
#   coreapi    Core API tree: metadata of everything, sha256 of data files (raw read; SQLite is never opened)
#   accounts   sha256 of passwd/group/shadow-less identity + sudoers
set -Eeuo pipefail
umask 077
OUT=${1:?usage: observe_host.sh <outdir>}
install -d -m 0700 "${OUT}"
UNITS="lilith-os-api-dev.service lilith-memory-broker.service lilith-memory-broker.socket lilith-authority-dev.service
 lilith-authority-dev.socket lilith-recovery-witness.service lilith-recovery-witness-owner.socket
 lilith-recovery-witness-signer.socket lilith-stage3-a2-final.service"
for u in ${UNITS}; do
  printf '%s ' "$u"
  systemctl show "$u" -p LoadState,ActiveState,SubState,MainPID,InvocationID,NRestarts,ExecMainStartTimestampMonotonic,NeedDaemonReload,UnitFileState \
    | tr '\n' ' '; echo
done > "${OUT}/services"
for u in ${UNITS}; do
  for f in $(systemctl show "$u" -p FragmentPath,DropInPaths --value); do [[ -f $f ]] && sha256sum "$f"; done
done | LC_ALL=C sort -u > "${OUT}/units"
# TCP listeners + UDP sockets on fixed ports. Unconnected UDP sockets in the ephemeral range (ip_local_port_range)
# are transient client sockets (resolver/NTP/agent queries), not services, and would make the comparison flaky.
read -r EPH_LO EPH_HI < /proc/sys/net/ipv4/ip_local_port_range
{ ss -Hltnu | awk -v lo="${EPH_LO}" -v hi="${EPH_HI}" '{n=split($5,a,":"); p=a[n]+0; if ($1=="udp" && p>=lo && p<=hi) next; print $1, $5}'     | grep -v -e '127.0.0.1:9901$' -e '127.0.0.1:9911$' | LC_ALL=C sort -u  # F8-owned listeners excluded
  for s in /run/lilith-memory/owner.sock /run/lilith-authority-dev/owner.sock /run/lilith-recovery-witness/owner.sock \
           /run/lilith-recovery-witness/signer.sock; do stat -c '%n %F %U:%G %a %i' "$s" 2>/dev/null || echo "$s ABSENT"; done
} > "${OUT}/sockets"
CUSTODY_ROOTS="/etc/credstore.encrypted /etc/lilith-authority-custody /var/lib/lilith-authority-custody /etc/lilith-authority-dev
 /var/lib/lilith-authority-dev /opt/lilith-authority-dev /etc/lilith-recovery-witness /var/lib/lilith-recovery-witness
 /etc/lilith-memory-broker /var/lib/lilith-memory-broker /opt/lilith-memory-broker /etc/lilith-os-dev /usr/local/lib/lilith-dev-deploy
 /opt/lilith-stage3-a2-final-v1 /opt/lilith-trusted-controls /run/lilith-memory /run/lilith-authority-dev /run/lilith-recovery-witness
 /run/credentials/lilith-authority-dev.service /run/credentials/lilith-recovery-witness.service /var/lib/systemd/credential.secret
 /etc/needrestart/conf.d /etc/tmpfiles.d"
{ for r in ${CUSTODY_ROOTS}; do
    if [[ -e $r ]]; then find "$r" -xdev -printf '%p %y %u:%g %m %s %i %T@\n'; else echo "$r ABSENT"; fi
  done
  find /usr/local/sbin -maxdepth 1 -name 'lilith-*' -printf '%p %y %u:%g %m %s %i %T@\n'
} | LC_ALL=C sort > "${OUT}/custody"
CORE=/home/lilith/.hermes/lilith-os-dev
{ find "${CORE}" -xdev -path "${CORE}/releases" -prune -o -path "${CORE}/api-venv" -prune -o -printf '%p %y %u:%g %m %s %i %T@\n'
  find "${CORE}/releases" -maxdepth 1 -printf '%p %y %u:%g %m %i\n'
  readlink "${CORE}/current"
  find "${CORE}/data" -type f -print0 | LC_ALL=C sort -z | xargs -0 -r sha256sum
} | LC_ALL=C sort > "${OUT}/coreapi"
{ sha256sum /etc/passwd /etc/group /etc/sudoers; find /etc/sudoers.d -type f -print0 | LC_ALL=C sort -z | xargs -0 -r sha256sum; } > "${OUT}/accounts"
(cd "${OUT}" && sha256sum services units sockets custody coreapi accounts > SECTIONS.sha256)
echo "F8_OBSERVED ${OUT}"
