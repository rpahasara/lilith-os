set -u
# Runs inside lilith-rehearsal-01 only. Every outbound attempt must fail. Uses the blank synthetic disk to prove a read-only attach behaves. No real data exists here.
FAILS=
fail() { echo "CHECK_FAIL $1"; FAILS="${FAILS} $1"; }
[ "$(hostname)" = lilith-rehearsal-01 ] || { echo "WRONG_HOST"; exit 3; }
blocked() { if timeout 6 bash -c "exec 3<>/dev/tcp/$2/$3" 2>/dev/null; then fail "reached_$1"; else echo "OK blocked $1"; fi; }
blocked public_https 142.250.4.100 443
blocked public_dns 8.8.8.8 53
blocked prod_ssh 10.20.0.2 22
blocked prod_api 10.20.0.2 8765
blocked dev_ssh 10.20.0.3 22
blocked dev_api 10.20.0.3 8765
blocked google_api 199.36.153.8 443
C=$(curl -s -o /dev/null -m 5 -w '%{http_code}' -H 'Metadata-Flavor: Google' http://169.254.169.254/computeMetadata/v1/instance/service-accounts/default/token)
[ "${C}" = 404 ] && echo "OK no_service_account_token" || fail "metadata_token_${C}"
[ "$(curl -s -m 5 -H 'Metadata-Flavor: Google' http://169.254.169.254/computeMetadata/v1/instance/service-accounts/ | wc -c)" -eq 0 ] && echo "OK no_service_accounts" || fail service_accounts_listed
[ -z "$(curl -s -m 5 -H "Metadata-Flavor: Google" http://169.254.169.254/computeMetadata/v1/instance/network-interfaces/0/access-configs/0/external-ip)" ] && echo "OK no_external_ip" || fail external_ip
python3 -c 'import sqlite3' && echo OK_sqlite || fail no_sqlite
DEV=/dev/disk/by-id/google-synthetic
sudo -n test -b ${DEV} || fail no_synthetic_disk
M=/mnt/rehearsal-synthetic
sudo -n mkfs.ext4 -q -F ${DEV} || fail mkfs
sudo -n mkdir -p ${M}; sudo -n mount ${DEV} ${M} || fail mount
echo TEST_ONLY | sudo -n tee ${M}/canary >/dev/null
sudo -n umount ${M}; sudo -n mount -o ro,noload ${DEV} ${M} || fail mount_ro
if sudo -n touch ${M}/write-test 2>/dev/null; then fail read_only_mount_writable; else echo "OK read_only_mount_refuses_writes"; fi
[ "$(sudo -n cat ${M}/canary)" = TEST_ONLY ] && echo OK_read_back || fail read_back
sudo -n umount ${M}
if [ -z "${FAILS}" ]; then echo "ISOLATION_PROBE PASS"; else echo "ISOLATION_PROBE FAIL:${FAILS}"; fi
