#!/usr/bin/env bash
# C-4 in-sandbox probe (gate G-7b; root). Runs ONE short-lived python probe inside the running gateway's cgroup (its
# BPF IP filter) and mount namespace (its InaccessiblePaths/RO binds), as user lilith. Every connection attempt below
# must be blocked; nothing is written except the read-only-ness checks (which must fail). The probe exits by itself.
set -uo pipefail
PID=$(systemctl show -p MainPID --value hermes-gateway-dev)
[[ ${PID} =~ ^[1-9][0-9]*$ ]] || { echo "F8_PROBE_FAIL gateway not running"; exit 1; }
CG=/sys/fs/cgroup$(awk -F: '$1=="0"{print $3}' /proc/${PID}/cgroup)
PY=/opt/hermes-gateway-dev/current/venv/bin/python
read -r -d '' PROBE <<'PYEOF'
import os, socket
res = []
def tcp(h, p):
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM); s.settimeout(3)
    try: s.connect((h, p)); return "OPEN"
    except OSError as e: return f"BLOCKED({type(e).__name__})"
    finally: s.close()
def udp_dns(h):
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM); s.settimeout(3)
    q = b"\x12\x34\x01\x00\x00\x01\x00\x00\x00\x00\x00\x00\x06google\x03com\x00\x00\x01\x00\x01"
    try: s.sendto(q, (h, 53)); s.recvfrom(512); return "OPEN"
    except OSError as e: return f"BLOCKED({type(e).__name__})"
    finally: s.close()
def resolve(name):
    try: socket.getaddrinfo(name, 80); return "OPEN"
    except OSError as e: return f"BLOCKED({type(e).__name__})"
def path(p):   # HIDDEN = absent in this namespace; NOACCESS = masked by InaccessiblePaths (exists, unreadable)
    try:
        os.stat(p)
    except FileNotFoundError:
        return "HIDDEN"
    except PermissionError:
        return "NOACCESS"
    try:
        os.listdir(p) if os.path.isdir(p) else open(p, "rb").close()
        return "VISIBLE"
    except OSError:
        return "NOACCESS"
def meta_resolution():
    # F8r3 (replaces the F8r2 P7 ACCEPTED_DEVIATION): GCE images map metadata.google.internal in /etc/hosts. The
    # sandbox may resolve it ONLY from that file, ONLY to 169.254.169.254 (P1 proves the connection is blocked);
    # any DNS-derived or other answer fails.
    try:
        addrs = sorted({a[4][0] for a in socket.getaddrinfo("metadata.google.internal", 80, socket.AF_INET)})
    except OSError as e:
        return f"BLOCKED({type(e).__name__})"
    hosts = [l.split() for l in open("/etc/hosts") if not l.lstrip().startswith("#")]
    in_hosts = any(len(f) > 1 and f[0] == "169.254.169.254" and "metadata.google.internal" in f[1:] for f in hosts)
    return f"HOSTS_ONLY({','.join(addrs)})" if addrs == ["169.254.169.254"] and in_hosts else f"RESOLVED({','.join(addrs)})"
def http(method, url):
    import urllib.request, urllib.error
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    try:
        with opener.open(urllib.request.Request(url, method=method), timeout=5) as r:
            return f"HTTP{r.status}"
    except urllib.error.HTTPError as e:
        return f"HTTP{e.code}"
    except OSError as e:
        return f"ERR({type(e).__name__})"
def connect_method():
    s = socket.create_connection(("127.0.0.1", 9911), timeout=5)
    try:
        s.sendall(b"CONNECT example.com:443 HTTP/1.1\r\nHost: example.com:443\r\n\r\n")
        return "HTTP" + s.recv(64).split(b" ")[1].decode()
    except (OSError, IndexError) as e:
        return f"ERR({type(e).__name__})"
    finally:
        s.close()
def can_write(p):
    try:
        with open(p, "a"): pass
        return "WRITABLE"
    except OSError as e: return f"DENIED({e.errno})"
res += [("P1 metadata 169.254.169.254:80", tcp("169.254.169.254", 80), "BLOCKED"),
        ("P2 internet 1.1.1.1:443", tcp("1.1.1.1", 443), "BLOCKED"),
        ("P3 PROD 10.20.0.2:8765", tcp("10.20.0.2", 8765), "BLOCKED"),
        (f"P4 own NIC IP {os.environ['NIC_IP']}:8765 (Core API via the VPC address)", tcp(os.environ["NIC_IP"], 8765), "BLOCKED"),
        ("P5 DNS stub 127.0.0.53:53/udp", udp_dns("127.0.0.53"), "BLOCKED"),
        ("P6 DNS public 8.8.8.8:53/udp", udp_dns("8.8.8.8"), "BLOCKED"),
        ("P7 metadata.google.internal: /etc/hosts only (169.254.169.254) or unresolvable", meta_resolution(), ("BLOCKED", "HOSTS_ONLY(169.254.169.254)")),
        ("P8 name resolution example.com", resolve("example.com"), "BLOCKED"),
        ("P9 Core API 127.0.0.1:8765 (permitted loopback)", tcp("127.0.0.1", 8765), "OPEN"),
        ("P10 D-Bus system bus socket", path("/run/dbus/system_bus_socket"), "HIDDEN"),
        ("P11 resolved varlink socket", path("/run/systemd/resolve/io.systemd.Resolve"), "HIDDEN"),
        ("P12 Core API tree /home/lilith/.hermes", path("/home/lilith/.hermes"), "HIDDEN"),
        ("P13 broker socket dir /run/lilith-memory", path("/run/lilith-memory"), "HIDDEN"),
        ("P14 credstore /etc/credstore.encrypted", path("/etc/credstore.encrypted"), "HIDDEN"),
        ("P15 config.yaml write", can_write("/home/lilith/.hermes-dev/config.yaml"), "DENIED"),
        ("P16 cron/jobs.json write", can_write("/home/lilith/.hermes-dev/cron/jobs.json"), "DENIED"),
        ("P17 router code write", can_write("/home/lilith/.hermes-dev/lilith_router/router.yaml"), "DENIED"),
        ("P18 provider gate 127.0.0.1:9911 (permitted loopback)", tcp("127.0.0.1", 9911), "OPEN"),
        ("P19 gate refuses non-allowlisted path GET /openai/v1/models", http("GET", "http://127.0.0.1:9911/openai/v1/models"), "HTTP404"),
        ("P20 gate refuses proxy use (CONNECT)", connect_method(), "HTTP405"),
        ("P21 gate credentials dir", path("/etc/hermes-provider-gate-dev/credentials"), "HIDDEN"),
        ("P22 gate state dir", path("/var/lib/private/hermes-provider-gate-dev"), "HIDDEN"),
        ("P23 systemd credentials (/run/credentials)", path("/run/credentials"), "HIDDEN")]
bad = 0
for name, got, want in res:
    ok = any(got.startswith(w) for w in want) if isinstance(want, tuple) else (got.startswith(want) or (want == "HIDDEN" and got == "NOACCESS"))
    want = "|".join(want) if isinstance(want, tuple) else want
    bad += not ok
    print(("PASS " if ok else "FAIL ") + f"{name}: {got}")
print(f"F8_PROBE_{'PASS' if not bad else 'FAIL'} {len(res) - bad}/{len(res)}")
raise SystemExit(1 if bad else 0)
PYEOF
# Join the gateway's cgroup (IP filter), then its mount namespace, drop to lilith, run the probe.
NIC_IP=$(ip -4 route get 1.1.1.1 2>/dev/null | awk '{for(i=1;i<NF;i++) if($i=="src") print $(i+1)}')
[[ -n ${NIC_IP} ]] || { echo "F8_PROBE_FAIL no NIC IP"; exit 1; }
sh -c 'echo $$ > "$1/cgroup.procs"; exec nsenter -t "$2" -m -- setpriv --reuid=lilith --regid=lilith --clear-groups env -i NIC_IP="$5" "$3" -I -B -c "$4"' \
  probe "${CG}" "${PID}" "${PY}" "${PROBE}" "${NIC_IP}"
