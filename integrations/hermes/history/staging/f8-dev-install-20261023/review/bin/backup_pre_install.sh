#!/usr/bin/env bash
# Gate G-1: pre-install backup + baseline observation. Read-only towards every existing service: it copies, it never
# stops, restarts or edits anything. Output: /var/backups/hermes-gateway-dev/pre-<UTC>/ (root 0700).
set -Eeuo pipefail
umask 077
TS=$(date -u +%Y%m%dT%H%M%SZ)
OUT=/var/backups/hermes-gateway-dev/pre-${TS}
install -d -o root -g root -m 0700 /var/backups/hermes-gateway-dev "${OUT}"
cd "${OUT}"
# 1. Existing DEV Hermes home (today: empty memories/) — full tar with ownership, plus a listing for the rollback diff.
tar --numeric-owner --xattrs --acls -C /home/lilith -cpf hermes-dev-home.tar .hermes-dev
find /home/lilith/.hermes-dev -printf '%M %u:%g %s %P\n' | LC_ALL=C sort -k4 > hermes-dev-home.listing
# 2. Core API DEV databases: consistent online copies through SQLite's backup API (no lock held beyond the copy).
CORE_DATA=/home/lilith/.hermes/lilith-os-dev/data
for db in "${CORE_DATA}"/*.db; do
  [[ -e ${db} ]] || continue
  /usr/bin/python3 -I -c 'import sqlite3,sys; s=sqlite3.connect(f"file:{sys.argv[1]}?mode=ro",uri=True); d=sqlite3.connect(sys.argv[2]); s.backup(d); d.close(); s.close()' \
    "${db}" "core-data-$(basename "${db}")"
done
# 3. Host baseline used by G-9 (must be identical after install except the new hermes-gateway-dev entries).
for u in lilith-os-api-dev lilith-memory-broker lilith-authority-dev lilith-recovery-witness; do
  systemctl show "$u" -p ActiveState,SubState,MainPID,NRestarts,ExecMainStartTimestamp,FragmentPath
done > services.baseline
ss -Hltnup | awk '{print $1,$5}' | LC_ALL=C sort > listen.baseline
sha256sum /etc/systemd/system/*.service /etc/systemd/system/*.socket /etc/passwd /etc/group /etc/sudoers.d/* > etc.baseline
ls -la /etc/systemd/system > systemd-dir.listing
free -m > mem.baseline; df -Pm / > disk.baseline
sha256sum * > SHA256SUMS
echo "F8_BACKUP_DONE ${OUT}"
