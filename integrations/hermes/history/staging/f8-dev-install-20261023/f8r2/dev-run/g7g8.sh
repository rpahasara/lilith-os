#!/usr/bin/env bash
# G-7 synthetic console smoke (incl. real Core API relay + capture-inactive), G-7b in-sandbox probe, G-8 retention.
set -uo pipefail
[[ $(hostname) == lilith-dev-01 ]] || { echo "WRONG HOST"; exit 1; }
R=/opt/hermes-gateway-dev/current
$R/venv/bin/python -I -B $R/bin/smoke_console.py --phase A --core-api | tee /var/backups/hermes-gateway-dev/G-7-smoke.txt | cut -c1-170
grep -q '^F8_SMOKE_PASS phase=A 22/22' /var/backups/hermes-gateway-dev/G-7-smoke.txt && echo G7_PASS || { echo G7_FAIL; exit 1; }
bash $R/bin/sandbox_probe.sh | tee /var/backups/hermes-gateway-dev/G-7b-probe.txt
grep -q '^F8_PROBE_PASS 17/17' /var/backups/hermes-gateway-dev/G-7b-probe.txt && echo G7B_PASS || { echo G7B_FAIL; exit 1; }
systemctl start hermes-gateway-dev-retention.service
res=$(systemctl show hermes-gateway-dev-retention.service -p Result --value)
journalctl --namespace=hermes-gateway-dev -u hermes-gateway-dev-retention --no-pager -n 3 | cut -c1-160
echo "gateway after tests: $(for k in ActiveState NRestarts MainPID; do systemctl show hermes-gateway-dev -p $k --value; done | paste -sd' ') ip_egress_bytes=$(systemctl show hermes-gateway-dev -p IPEgressBytes --value)"
[[ $res == success ]] && echo G8_PASS || echo G8_FAIL
