#!/usr/bin/env bash
# F8r3 G-7c: provider-gate sandbox probe (root). Runs one short-lived python probe inside the gate's cgroup (its BPF IP
# filter) and mount namespace, as the gate's dynamic uid. Only DENIED targets are attempted (no public connection is
# made from DEV by this probe). Also proves the key is held as a credential file, not in the gate's environment.
set -uo pipefail
PID=$(systemctl show -p MainPID --value hermes-provider-gate-dev)
[[ ${PID} =~ ^[1-9][0-9]*$ ]] || { echo "F8_GATE_PROBE_FAIL gate not running"; exit 1; }
UID_G=$(awk '/^Uid:/{print $2}' /proc/${PID}/status); GID_G=$(awk '/^Gid:/{print $2}' /proc/${PID}/status)
CG=/sys/fs/cgroup$(awk -F: '$1=="0"{print $3}' /proc/${PID}/cgroup)
PY=/opt/hermes-gateway-dev/current/venv/bin/python
KEYFILE=/etc/hermes-provider-gate-dev/credentials/groq-api-key
env_has_key=no
if [[ -s ${KEYFILE} ]] && grep -qF -- "$(tr -d '\n' < ${KEYFILE})" /proc/${PID}/environ; then env_has_key=yes; fi
echo "gate pid=${PID} uid=${UID_G} (dynamic) key_in_environ=${env_has_key}"
read -r -d '' PROBE <<'PYEOF'
import os, socket
def tcp(h, p):
    s = socket.socket(); s.settimeout(3)
    try: s.connect((h, p)); return "OPEN"
    except OSError as e: return f"BLOCKED({type(e).__name__})"
    finally: s.close()
def path(p):
    try: os.stat(p)
    except FileNotFoundError: return "HIDDEN"
    except PermissionError: return "NOACCESS"
    try: os.listdir(p) if os.path.isdir(p) else open(p, "rb").close(); return "VISIBLE"
    except OSError: return "NOACCESS"
cred = os.path.join("/run/credentials/hermes-provider-gate-dev.service", "groq-api-key")
res = [("Q1 metadata 169.254.169.254:80", tcp("169.254.169.254", 80), "BLOCKED"),
       ("Q2 PROD 10.20.0.2:8765", tcp("10.20.0.2", 8765), "BLOCKED"),
       ("Q3 VPC gateway 10.20.0.1:80", tcp("10.20.0.1", 80), "BLOCKED"),
       ("Q4 RFC1918 192.168.0.1:80", tcp("192.168.0.1", 80), "BLOCKED"),
       ("Q5 CGNAT 100.64.0.1:80", tcp("100.64.0.1", 80), "BLOCKED"),
       ("Q6 loopback other than 127.0.0.1 (127.0.0.2:8765)", tcp("127.0.0.2", 8765), "BLOCKED"),
       ("Q7 key file /etc/hermes-provider-gate-dev/credentials", path("/etc/hermes-provider-gate-dev/credentials"), "HIDDEN"),
       ("Q8 HERMES_HOME /home/lilith/.hermes-dev", path("/home/lilith/.hermes-dev"), "HIDDEN"),
       ("Q9 gateway pins /etc/hermes-gateway-dev", path("/etc/hermes-gateway-dev"), "HIDDEN"),
       ("Q10 own credential readable by the gate uid only", path(cred), "VISIBLE")]
bad = 0
for n, got, want in res:
    ok = got.startswith(want) or (want == "HIDDEN" and got == "NOACCESS")
    bad += not ok; print(("PASS " if ok else "FAIL ") + f"{n}: {got}")
raise SystemExit(1 if bad else 0)
PYEOF
sh -c 'echo $$ > "$1/cgroup.procs"; exec nsenter -t "$2" -m -- setpriv --reuid="$3" --regid="$4" --clear-groups env -i "$5" -I -B -c "$6"' \
  probe "${CG}" "${PID}" "${UID_G}" "${GID_G}" "${PY}" "${PROBE}"; rc=$?
lil=$(runuser -u lilith -- cat /run/credentials/hermes-provider-gate-dev.service/groq-api-key >/dev/null 2>&1 && echo READABLE || echo DENIED)
echo "uid lilith -> gate credential: ${lil}"
[[ ${rc} -eq 0 && ${env_has_key} == no && ${lil} == DENIED ]] && echo "F8_GATE_PROBE_PASS" || { echo "F8_GATE_PROBE_FAIL"; exit 1; }
