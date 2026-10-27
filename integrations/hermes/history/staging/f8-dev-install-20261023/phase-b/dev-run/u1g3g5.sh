#!/usr/bin/env bash
# U-1 preserve F8r2 -> G-3 install f8r4 (staged) -> G-3b DR-5 -> G-4 F7 suite (lilith) -> G-5 console token + verify --full.
# Stops at the first failure; no automatic rollback (owner-reviewed R-steps are run separately).
set -uo pipefail
[[ $(hostname) == lilith-dev-01 ]] || { echo "WRONG HOST"; exit 1; }
P=/var/tmp/f8/hermes-gateway-dev-f293e72-f8r4; R=/opt/hermes-gateway-dev/current; B=/var/backups/hermes-gateway-dev
echo "== U-1"
F8R2_RELEASE_SHA=ffaed494e2643b2d56533f63a919daebaa0b8a78e5ada8deca614c92cf96cf12 bash $P/bin/preserve_f8r2.sh > $B/U-1-preserve.log 2>&1; rc=$?
cat $B/U-1-preserve.log | grep -E 'F8R2_|F8_|HOLD|FAIL' | cut -c1-220
grep -q '^F8R2_PRESERVED ' $B/U-1-preserve.log && [[ $rc -eq 0 ]] || { echo "U1_FAIL rc=$rc"; tail -5 $B/U-1-preserve.log; exit 1; }
echo "HH after preserve: $(ls -A /home/lilith/.hermes-dev | paste -sd' ')"; echo U1_PASS
echo "== G-3"
bash $P/bin/install.sh > $B/G-3-f8r4-install.log 2>&1; rc=$?
grep -E '^--- |F8_' $B/G-3-f8r4-install.log | cut -c1-200
grep -q '^F8_INSTALL_STAGED f293e72-f8r4$' $B/G-3-f8r4-install.log && [[ $rc -eq 0 ]] || { echo "G3_FAIL rc=$rc"; tail -5 $B/G-3-f8r4-install.log; exit 1; }
fails=$(grep '^F8_VERIFY_FAIL' $B/G-3-f8r4-install.log | grep -vc 'MISSING /home/lilith/.hermes-dev/.env')
[[ $fails -eq 0 ]] || { echo "G3_FAIL unexpected verify failures"; exit 1; }
echo G3_PASS
echo "== G-3b"
bash $P/bin/dr5_check.sh $B/dr5-f8r4-installed.txt | tail -1 | grep -q '^F8_DR5_EQUAL ' && echo G3B_PASS || { echo G3B_FAIL; exit 1; }
echo "== G-4"
T=$(mktemp -d /var/tmp/f8-g4-XXXXXX)
ln -s $R/src $T/hermes-agent; mkdir $T/hermes-home-dev $T/tests
cp -a $P/home/lilith_router $P/home/plugins $T/hermes-home-dev/
cp $P/tests/f7-home/config.yaml $T/hermes-home-dev/; cp $P/tests/f7-home/router.yaml $T/hermes-home-dev/lilith_router/
cp $P/tests/test_f7_offline.py $T/tests/; chown -R lilith:lilith $T; chmod 700 $T
runuser -u lilith -- env -i PATH=/usr/bin:/bin HOME=$T PYTHONUNBUFFERED=1 $R/venv/bin/python -B $T/tests/test_f7_offline.py > $B/G-4-f8r4-f7.log 2>&1; rc=$?
rm -rf -- "$T"
grep -E '^Ran |^OK|^FAILED' $B/G-4-f8r4-f7.log
[[ $rc -eq 0 ]] && grep -q '^OK$' $B/G-4-f8r4-f7.log && echo G4_PASS || { echo G4_FAIL; exit 1; }
echo "== G-5"
bash $P/bin/provision_console_token.sh || { echo G5_FAIL; exit 1; }
$R/venv/bin/python -I -B $R/bin/verify_release.py --full; vrc=$?
echo "credentials dir: $(stat -c '%U:%G %a' /etc/hermes-provider-gate-dev/credentials) entries=$(ls -A /etc/hermes-provider-gate-dev/credentials | wc -l)"
echo "units: gw=$(systemctl show hermes-gateway-dev -p ActiveState,UnitFileState --value | paste -sd/) gate=$(systemctl show hermes-provider-gate-dev -p ActiveState,UnitFileState --value | paste -sd/)"
echo "router: $(grep -E '^(mode|cognitive_enabled|canonical_ltm_enabled):' /home/lilith/.hermes-dev/lilith_router/router.yaml | paste -sd' ')"
[[ $vrc -eq 0 ]] && echo G5_PASS || echo G5_FAIL
