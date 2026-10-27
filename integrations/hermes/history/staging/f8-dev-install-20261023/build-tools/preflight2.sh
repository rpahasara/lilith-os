#!/usr/bin/env bash
# F8 DEV preflight pass 2: READ-ONLY (socket ACLs, egress config, journald, Core API env usage).
set -u
s() { echo; echo "=== $* ==="; }
for u in lilith-memory-broker.socket lilith-authority-dev.socket lilith-recovery-witness-owner.socket lilith-recovery-witness-signer.socket; do
  s "SOCKET $u"; systemctl show "$u" -p ActiveState,Listen,SocketUser,SocketGroup,SocketMode,DirectoryMode,DropInPaths
  f=$(systemctl show "$u" -p FragmentPath --value); grep -vE '^\s*(#|$)' "$f"; for d in $(systemctl show "$u" -p DropInPaths --value); do echo "--- $d"; grep -vE '^\s*(#|$)' "$d"; done
done
s RUN_SOCKETS; sudo -n find /run -maxdepth 3 -type s -printf '%M %u:%g %p\n' 2>/dev/null | grep -iE 'lilith|broker|authority|witness'
sudo -n find /run -maxdepth 2 -type d -iname '*lilith*' -printf '%M %u:%g %p\n'
s LILITH_ACCESS_TEST
for p in /run/lilith-memory-broker /run/lilith-authority-dev /var/lib/lilith-memory-broker /etc/lilith-memory-broker /opt/lilith-memory-broker /etc/credstore.encrypted /var/lib/lilith-recovery-witness; do
  printf '%s: ' "$p"; sudo -n -u lilith test -r "$p" && echo -n 'r ' || echo -n '- '; sudo -n -u lilith test -x "$p" && echo x || echo -; done
s STAGE3_UNIT; grep -vE '^\s*(#|$)' /etc/systemd/system/lilith-stage3-a2-final.service
s AUTH_DROPIN; cat /etc/systemd/system/lilith-authority-dev.service.d/*.conf
s CORE_API_RELEASE; ls -la /home/lilith/.hermes/lilith-os-dev/current/ 2>&1 | head; sudo -n du -sh /home/lilith/.hermes/lilith-os-dev/releases /home/lilith/.hermes/lilith-os-dev/api-venv /home/lilith/.hermes/lilith-os-dev/data 2>&1
sudo -n ls -la /home/lilith/.hermes/lilith-os-dev/data
s NEEDRESTART_CONF; sudo -n grep -vE '^\s*(#|$)' /etc/needrestart/conf.d/lilith-authority-sensitive.conf
s UNATTENDED; grep -vhE '^\s*(//|$)' /etc/apt/apt.conf.d/50unattended-upgrades /etc/apt/apt.conf.d/20auto-upgrades 2>/dev/null | head -30
s SUDOERS; sudo -n ls -la /etc/sudoers.d/; sudo -n grep -l lilith /etc/sudoers.d/* 2>/dev/null
s TMP; df -h /tmp /var/tmp /dev/shm | tail -3
s LOGIN_LILITH; sudo -n loginctl show-user lilith -p Linger 2>&1; ls /var/lib/systemd/linger 2>&1
s CRON_LILITH; sudo -n crontab -l -u lilith 2>&1
s DONE
