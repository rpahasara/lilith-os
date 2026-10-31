set -u
# Runs as root on lilith-rehearsal-01 only. The metadata server answers DNS, and no VPC firewall rule can stop that: traffic to it never leaves the host. This drops it in the guest, the only place it can be dropped. HTTP metadata stays, because OS Login needs it.
# The rules last until reboot, so G3-B checks them again. guest_dns_check.sh is the proof; this script only records that the path was open first and adds the rules.
[ "$(hostname)" = lilith-rehearsal-01 ] || { echo "DNS_GUARD FAIL wrong host"; exit 1; }
BEFORE=$(python3 -I -c '
import socket, struct
q = struct.pack(">HHHHHH", 0x1111, 0x0100, 1, 0, 0, 0) + b"\x07example\x03org\x00" + struct.pack(">HH", 1, 1)
u = socket.socket(socket.AF_INET, socket.SOCK_DGRAM); u.settimeout(4)
try:
    u.sendto(q, ("169.254.169.254", 53)); u.recvfrom(512); print("OPEN")
except OSError:
    print("CLOSED")')
echo "BEFORE_GUARD_DNS ${BEFORE}"
[ "${BEFORE}" = OPEN ] || { echo "DNS_GUARD FAIL the control did not answer, so a later block would prove nothing"; exit 1; }
for p in udp tcp; do
  iptables -C OUTPUT -d 169.254.169.254 -p ${p} --dport 53 -j DROP 2>/dev/null || iptables -I OUTPUT 1 -d 169.254.169.254 -p ${p} --dport 53 -j DROP || { echo "DNS_GUARD FAIL rule ${p}"; exit 1; }
done
echo "DNS_GUARD APPLIED"
