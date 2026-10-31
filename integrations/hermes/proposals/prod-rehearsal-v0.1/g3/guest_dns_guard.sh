set -u
# Runs as root on lilith-rehearsal-01 only. The metadata server answers DNS, and no VPC firewall rule can stop that: traffic to it never leaves the host. This drops it in the guest, the only place it can be dropped. HTTP metadata stays, because OS Login needs it.
[ "$(hostname)" = lilith-rehearsal-01 ] || { echo "GUARD_STOPPED wrong host"; exit 1; }
BEFORE=$(timeout 8 getent hosts example.com | wc -l)
for p in udp tcp; do
  iptables -C OUTPUT -d 169.254.169.254 -p ${p} --dport 53 -j DROP 2>/dev/null || iptables -I OUTPUT 1 -d 169.254.169.254 -p ${p} --dport 53 -j DROP
done
resolvectl flush-caches 2>/dev/null
AFTER=$(timeout 8 getent hosts example.org | wc -l)
CODE=$(curl -s -o /dev/null -m 5 -w '%{http_code}' -H 'Metadata-Flavor: Google' http://169.254.169.254/computeMetadata/v1/instance/id)
echo "RESOLVED_BEFORE ${BEFORE} RESOLVED_AFTER ${AFTER} METADATA_HTTP ${CODE}"
if [ "${AFTER}" = 0 ] && [ "${CODE}" = 200 ]; then echo "DNS_GUARD PASS"; else echo "DNS_GUARD FAIL"; fi
