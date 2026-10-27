#!/usr/bin/env bash
# F8 DEV preflight: READ-ONLY. Writes nothing; contacts only the local metadata server.
set -u
s() { echo; echo "=== $* ==="; }
s HOST; hostname; date -u +%FT%TZ; cat /proc/sys/kernel/random/boot_id; uptime
s OS; cat /etc/os-release | grep -E '^(PRETTY_NAME|VERSION_ID|VERSION_CODENAME)='; uname -r; systemctl --version | head -1
s RESOURCES; nproc; free -m; df -hT / /home /var /tmp 2>/dev/null; df -i / | tail -1
s SWAP; swapon --show; cat /proc/sys/vm/swappiness
s PYTHON; for p in python3 python3.11 python3.12 python3.13 python3.14 uv; do printf '%s: ' $p; command -v $p && $p --version 2>&1 | head -1; echo; done
ls -d /usr/lib/python3* 2>/dev/null; ls /home/lilith/.local/bin 2>/dev/null; sudo -n ls /root/.local/bin 2>/dev/null
s APT_POLICY; apt-cache policy python3.11 python3 2>/dev/null | grep -E '^[a-z]|Installed|Candidate'
s USERS; id lilith; getent group lilith; getent passwd | awk -F: '$3>=900 && $3<65534{print $1,$3,$4,$6,$7}'
s UNITS_RUNNING; systemctl list-units --type=service --state=running --no-legend --plain | awk '{print $1}'
s UNITS_LILITH; systemctl list-unit-files --no-legend --plain | grep -iE 'lilith|hermes|broker|authority|witness|signer'
s TIMERS; systemctl list-timers --all --no-legend --plain | head -30
for u in lilith-os-api-dev lilith-memory-broker lilith-authority-dev lilith-recovery-witness hermes-gateway hermes-gateway-dev; do
  s "UNIT $u"; systemctl show "$u" -p LoadState,ActiveState,SubState,User,Group,MainPID,ExecMainStartTimestamp,NRestarts,FragmentPath,DropInPaths,WorkingDirectory,ProtectSystem,ProtectHome,ReadWritePaths,ReadOnlyPaths,InaccessiblePaths,NoNewPrivileges,PrivateTmp,MemoryMax,MemoryCurrent,CPUQuotaPerSecUSec,IPAddressDeny,IPAddressAllow,RestrictAddressFamilies,UMask,StateDirectory,LogsDirectory 2>/dev/null
  f=$(systemctl show "$u" -p FragmentPath --value 2>/dev/null); [ -n "$f" ] && [ -f "$f" ] && { echo "--- $f sha256 $(sha256sum "$f" | cut -c1-16)"; grep -vE '^\s*(#|$)' "$f" | sed -E 's/(TOKEN|KEY|SECRET|PASSWORD)=.*/\1=<redacted>/I'; }
done
s LISTEN; sudo -n ss -Hltnup | awk '{print $1,$5,$7}' | sed -E 's/pid=([0-9]+),fd=[0-9]+/pid=\1/g'
s LISTEN_8765_9901; sudo -n ss -Hltnp '( sport = :8765 or sport = :9901 )'
s HOST_FIREWALL; sudo -n nft list ruleset 2>&1 | head -80; sudo -n ufw status verbose 2>&1 | head -20; sudo -n iptables -S 2>&1 | head -30
s NET; ip -br addr; ip route
s GCE_METADATA
H='Metadata-Flavor: Google'; M=http://169.254.169.254/computeMetadata/v1/instance
for k in name machine-type zone tags network-interfaces/0/ip network-interfaces/0/network network-interfaces/0/access-configs/0/external-ip; do printf '%s: ' $k; curl -s -m 3 -H "$H" "$M/$k" ; echo; done
s FS_LAYOUT
sudo -n ls -la /home/lilith /home/lilith/.hermes /home/lilith/.hermes-dev /home/lilith/.hermes-dev/memories /opt /srv 2>&1
sudo -n find /home/lilith/.hermes-dev -maxdepth 3 -printf '%M %u:%g %s %p\n' 2>&1 | head -40
sudo -n ls -la /home/lilith/.hermes/lilith-os-dev /etc/lilith-os-dev 2>&1
sudo -n ls -la /etc/systemd/system | grep -iE 'lilith|hermes|broker|authority|witness'
s HERMES_PRESENT; command -v hermes; sudo -n find / -xdev -maxdepth 5 \( -name 'hermes-agent' -o -name 'hermes_cli' -o -name 'hermes-gateway*' \) 2>/dev/null | head
s EGRESS_CONFIG; cat /etc/resolv.conf | grep -v '^#'; sudo -n ls /etc/apt/sources.list.d/ 2>/dev/null
s JOURNALD; grep -vE '^\s*(#|$)' /etc/systemd/journald.conf; ls /etc/systemd/journald.conf.d/ 2>/dev/null; sudo -n journalctl --disk-usage
s LOGROTATE; ls /etc/logrotate.d/
s SECURITY; cat /sys/kernel/security/lsm 2>/dev/null; echo; sudo -n aa-status 2>&1 | head -3; cat /proc/sys/kernel/unprivileged_userns_clone 2>/dev/null; mount | grep -E ' / | /home | /tmp '
s NEEDRESTART; ls -la /var/run/reboot-required 2>&1; sudo -n ls /etc/needrestart/conf.d/ 2>&1
s DONE
