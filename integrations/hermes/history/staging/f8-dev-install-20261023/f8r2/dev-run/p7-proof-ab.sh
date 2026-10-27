#!/usr/bin/env bash
# P7 exception proof + direct network-denial proof + revalidation (DEV, root). Changes nothing on the host; writes only
# evidence under /var/backups/hermes-gateway-dev/p7/. Probe processes join the gateway cgroup + mount ns as lilith.
set -u
[[ $(hostname) == lilith-dev-01 ]] || { echo "WRONG HOST"; exit 1; }
B=/var/backups/hermes-gateway-dev; O=$B/p7; install -d -m 0700 $O
P=/var/tmp/f8/hermes-gateway-dev-f293e72-f8r2; R=/opt/hermes-gateway-dev/current; PY=$R/venv/bin/python
PID=$(systemctl show -p MainPID --value hermes-gateway-dev)
CG=/sys/fs/cgroup$(awk -F: '$1=="0"{print $3}' /proc/$PID/cgroup)
insandbox() { bash -c 'echo $$ > "$1/cgroup.procs"; pid=$2; shift 2; exec nsenter -t "$pid" -m -- setpriv --reuid=lilith --regid=lilith --clear-groups "$@"' x "$CG" "$PID" "$@"; }
acct() { for k in IPIngressPackets IPEgressPackets IPIngressBytes IPEgressBytes; do printf '%s=%s ' $k "$(systemctl show hermes-gateway-dev -p $k --value)"; done; }
{
echo "== A. P7 source (independent of the packaged probe)"
echo "host /etc/hosts:      $(grep -n 'metadata.google.internal' /etc/hosts)"
echo "sandbox /etc/hosts:   $(insandbox grep -n 'metadata.google.internal' /etc/hosts)"
echo "sandbox nsswitch:     $(insandbox grep '^hosts' /etc/nsswitch.conf)"
echo "files-only lookup:    $(insandbox getent -s files hosts metadata.google.internal || echo NOT_FOUND)"
echo "dns-only lookup:      $(insandbox timeout 20 getent -s dns hosts metadata.google.internal || echo "FAILED rc=$? (DNS blocked)")"
echo "dns-only example.com: $(insandbox timeout 20 getent -s dns hosts example.com || echo "FAILED rc=$? (DNS blocked)")"
a0=$(acct); insandbox $PY -I -c 'import socket; print("getaddrinfo:", sorted({a[4][0] for a in socket.getaddrinfo("metadata.google.internal", 80)}))'; a1=$(acct)
echo "IP accounting before: $a0"; echo "IP accounting after:  $a1"
[[ "$a0" == "$a1" ]] && echo "P7_LOOKUP_NO_PACKETS (gateway cgroup counters unchanged across the lookup)" || echo "P7_COUNTERS_CHANGED"
echo
echo "== B. Direct network-denial proof inside the sandbox"
insandbox $PY -I -c '
import socket
def tcp(h,p):
    s=socket.socket(); s.settimeout(4)
    try: s.connect((h,p)); return "OPEN"
    except OSError as e: return "BLOCKED("+type(e).__name__+")"
    finally: s.close()
def dns(h):
    s=socket.socket(socket.AF_INET,socket.SOCK_DGRAM); s.settimeout(4)
    q=b"\x12\x34\x01\x00\x00\x01\x00\x00\x00\x00\x00\x00\x06google\x03com\x00\x00\x01\x00\x01"
    try: s.sendto(q,(h,53)); s.recvfrom(512); return "OPEN"
    except OSError as e: return "BLOCKED("+type(e).__name__+")"
    finally: s.close()
t=[("metadata 169.254.169.254:80 (by IP)",tcp("169.254.169.254",80)),
   ("metadata via hosts name metadata.google.internal:80",tcp("metadata.google.internal",80)),
   ("metadata DNS 169.254.169.254:53/udp",dns("169.254.169.254")),
   ("DNS stub 127.0.0.53:53/udp",dns("127.0.0.53")),("DNS stub 127.0.0.54:53/udp",dns("127.0.0.54")),
   ("public DNS 8.8.8.8:53/udp",dns("8.8.8.8")),("internet 1.1.1.1:443",tcp("1.1.1.1",443)),
   ("internet 142.250.0.1:443",tcp("142.250.0.1",443)),("PROD 10.20.0.2:8765",tcp("10.20.0.2",8765)),
   ("PROD 10.20.0.2:22",tcp("10.20.0.2",22)),("VPC gateway 10.20.0.1:80",tcp("10.20.0.1",80)),
   ("own NIC 10.20.0.3:8765",tcp("10.20.0.3",8765)),("own NIC 10.20.0.3:22",tcp("10.20.0.3",22))]
bad=0
for n,r in t:
    ok=r.startswith("BLOCKED"); bad+= not ok; print(("BLOCKED " if ok else "OPEN!!  ")+n+": "+r)
print("NETWORK_DENIAL_PROOF", "PASS" if not bad else "FAIL", f"{len(t)-bad}/{len(t)}")'
echo "unit network policy: $(systemctl show hermes-gateway-dev -p IPAddressAllow,IPAddressDeny,RestrictAddressFamilies --value | paste -sd' | ')"
echo "established non-loopback sockets of gateway: [$(ss -Htnp state established | grep "pid=$PID," | grep -v '127.0.0.1' | paste -sd';')]"
echo
} > $O/proof-ab.txt 2>&1
cat $O/proof-ab.txt
echo "PROOF_AB_SHA $(sha256sum < $O/proof-ab.txt | cut -c1-64)"
