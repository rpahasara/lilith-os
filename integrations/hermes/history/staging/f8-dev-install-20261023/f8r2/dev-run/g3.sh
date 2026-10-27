#!/usr/bin/env bash
# G-3 install (staged; C-3 guarded reload) + G-3b DR-5 + G-4 F7 suite (as lilith, temp dir under /var/tmp/f8-g4-*).
set -uo pipefail
[[ $(hostname) == lilith-dev-01 ]] || { echo "WRONG HOST"; exit 1; }
P=/var/tmp/f8/hermes-gateway-dev-f293e72-f8r2; R=/opt/hermes-gateway-dev/current
bash $P/bin/install.sh > /var/backups/hermes-gateway-dev/G-3-install.log 2>&1; rc=$?
grep -E '^--- |F8_' /var/backups/hermes-gateway-dev/G-3-install.log
grep -q '^F8_INSTALL_STAGED f293e72-f8r2$' /var/backups/hermes-gateway-dev/G-3-install.log && [[ $rc -eq 0 ]] || { echo "G3_FAIL rc=$rc"; tail -5 /var/backups/hermes-gateway-dev/G-3-install.log; exit 1; }
fails=$(grep '^F8_VERIFY_FAIL' /var/backups/hermes-gateway-dev/G-3-install.log | grep -vc 'MISSING /home/lilith/.hermes-dev/.env')
[[ $fails -eq 0 ]] || { echo "G3_FAIL unexpected verify failures"; exit 1; }
echo G3_PASS
bash $P/bin/dr5_check.sh /var/backups/hermes-gateway-dev/dr5-installed.txt || { echo G3B_FAIL; exit 1; }
echo G3B_PASS
B=$(mktemp -d /var/tmp/f8-g4-XXXXXX)
ln -s $R/src $B/hermes-agent; mkdir $B/hermes-home-dev $B/tests
cp -a $P/home/lilith_router $P/home/plugins $B/hermes-home-dev/
cp $P/tests/f7-home/config.yaml $B/hermes-home-dev/; cp $P/tests/f7-home/router.yaml $B/hermes-home-dev/lilith_router/
cp $P/tests/test_f7_offline.py $B/tests/; chown -R lilith:lilith $B; chmod 700 $B
runuser -u lilith -- env -i PATH=/usr/bin:/bin HOME=$B PYTHONUNBUFFERED=1 $R/venv/bin/python -B $B/tests/test_f7_offline.py > /var/backups/hermes-gateway-dev/G-4-f7.log 2>&1; rc=$?
rm -rf -- "$B"
grep -E ' \.\.\. |^Ran |^OK|^FAILED' /var/backups/hermes-gateway-dev/G-4-f7.log
[[ $rc -eq 0 ]] && grep -q '^OK$' /var/backups/hermes-gateway-dev/G-4-f7.log && echo G4_PASS || echo G4_FAIL
