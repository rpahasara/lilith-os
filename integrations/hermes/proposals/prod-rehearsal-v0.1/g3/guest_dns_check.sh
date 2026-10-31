set -u
# Read-only, as root on lilith-rehearsal-01. Proves the guard is active now: both rules present, and the metadata server's DNS unreachable directly and through the resolver, while its HTTP still works.
[ "$(hostname)" = lilith-rehearsal-01 ] || { echo "DNS_CHECK FAIL wrong host"; exit 1; }
FAILS=
fail() { echo "CHECK_FAIL $1"; FAILS="${FAILS} $1"; }
for p in udp tcp; do iptables -C OUTPUT -d 169.254.169.254 -p ${p} --dport 53 -j DROP 2>/dev/null && echo "OK rule_${p}" || fail "rule_${p}"; done
python3 -I - <<'PY' | tee /dev/stderr 2>&1 | sort -u > /run/dns-check.out
import socket, struct
q = struct.pack(">HHHHHH", 0x4321, 0x0100, 1, 0, 0, 0) + b"\x07example\x03net\x00" + struct.pack(">HH", 1, 1)
u = socket.socket(socket.AF_INET, socket.SOCK_DGRAM); u.settimeout(4)
try:
    u.sendto(q, ("169.254.169.254", 53)); u.recvfrom(512); print("RAW_UDP ANSWERED")
except OSError:
    print("RAW_UDP BLOCKED")
t = socket.socket(); t.settimeout(4)
try:
    t.connect(("169.254.169.254", 53)); print("RAW_TCP CONNECTED")
except OSError:
    print("RAW_TCP BLOCKED")
PY
grep -qx 'RAW_UDP BLOCKED' /run/dns-check.out || fail raw_udp
grep -qx 'RAW_TCP BLOCKED' /run/dns-check.out || fail raw_tcp
rm -f /run/dns-check.out
resolvectl flush-caches 2>/dev/null
[ "$(timeout 8 getent hosts example.edu | wc -l)" = 0 ] && echo OK_resolver_blocked || fail resolver_answers
[ "$(curl -s -o /dev/null -m 5 -w '%{http_code}' -H 'Metadata-Flavor: Google' http://169.254.169.254/computeMetadata/v1/instance/id)" = 200 ] && echo OK_metadata_http || fail metadata_http
if [ -z "${FAILS}" ]; then echo "DNS_CHECK PASS"; else echo "DNS_CHECK FAIL:${FAILS}"; fi
