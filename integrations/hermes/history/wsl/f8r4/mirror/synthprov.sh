#!/usr/bin/env bash
# WSL mirror ONLY: set up / tear down the synthetic Groq environment (refuses on lilith-dev-01).
#   synthprov.sh up | down
# up:   dummy interface f8test with 1.2.3.4/32 (a global unicast address, so the gate's non-global check is exercised
#       for real); /etc/hosts "1.2.3.4 api.groq.com"; a throwaway test CA added to the system trust store; a synthetic
#       key "gsk_F8R3SYNTH…" (never a real key); fake_groq.py as a transient unit.
set -Eeuo pipefail
[[ $(hostname) != lilith-dev-01 ]] || { echo refused; exit 1; }
D=/root/f8r4/synth; MARK="# f8r3-synthetic-provider"
case "${1:-}" in
up)
  mkdir -p $D; cd $D; : > requests.jsonl; echo ok > mode
  if [[ ! -f ca.pem ]]; then
    openssl req -x509 -newkey rsa:2048 -nodes -days 3 -subj "/CN=F8R3 SYNTHETIC TEST CA" -keyout ca.key -out ca.pem 2>/dev/null
    openssl req -newkey rsa:2048 -nodes -subj "/CN=api.groq.com" -keyout srv.key -out srv.csr 2>/dev/null
    printf 'subjectAltName=DNS:api.groq.com\nbasicConstraints=CA:FALSE\nextendedKeyUsage=serverAuth\n' > ext.cnf
    openssl x509 -req -in srv.csr -CA ca.pem -CAkey ca.key -CAcreateserial -days 3 -extfile ext.cnf -out srv.pem 2>/dev/null
  fi
  printf 'gsk_F8R3SYNTHETICTESTKEY0000000000000000000000\n' > synthetic-key; chmod 600 synthetic-key
  ip link show f8test >/dev/null 2>&1 || { ip link add f8test type dummy; ip addr add 1.2.3.4/32 dev f8test; ip link set f8test up; }
  grep -q "$MARK" /etc/hosts || printf '1.2.3.4 api.groq.com %s\n' "$MARK" >> /etc/hosts
  cp ca.pem /usr/local/share/ca-certificates/f8r3-synthetic-test-ca.crt; update-ca-certificates >/dev/null 2>&1
  systemctl stop f8r3-fake-groq 2>/dev/null || true; systemctl reset-failed f8r3-fake-groq 2>/dev/null || true
  systemd-run --unit=f8r3-fake-groq --quiet /usr/bin/python3 -I -B /root/f8r4/mirror/fake_groq.py 1.2.3.4 $D/srv.pem $D/srv.key $D/synthetic-key $D
  sleep 1; systemctl is-active f8r3-fake-groq ;;
down)
  systemctl stop f8r3-fake-groq 2>/dev/null || true
  sed -i "/$MARK/d" /etc/hosts
  rm -f /usr/local/share/ca-certificates/f8r3-synthetic-test-ca.crt; update-ca-certificates --fresh >/dev/null 2>&1
  ip link del f8test 2>/dev/null || true; echo "synthetic provider removed" ;;
*) echo "usage: up|down"; exit 2 ;;
esac
