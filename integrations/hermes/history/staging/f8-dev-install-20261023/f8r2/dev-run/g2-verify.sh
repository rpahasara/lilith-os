#!/usr/bin/env bash
# G-2 (DEV, root): move the transferred package into /var/tmp/f8 (0700), verify tarball + MANIFEST. No other change.
set -Eeuo pipefail
[[ $(hostname) == lilith-dev-01 ]] || { echo "WRONG HOST"; exit 1; }
N=hermes-gateway-dev-f293e72-f8r2
[[ ! -e /var/tmp/f8 ]] || { echo "G2_FAIL /var/tmp/f8 already exists"; exit 1; }
install -d -o root -g root -m 0700 /var/tmp/f8
mv /var/tmp/$N.tar.gz /var/tmp/$N.tar.gz.sha256 /var/tmp/f8/
chown root:root /var/tmp/f8/*; chmod 0600 /var/tmp/f8/*
cd /var/tmp/f8
[[ $(cut -c1-64 $N.tar.gz.sha256) == 269dde950eb024155235b3237a4658c93039975c600fa2f40d638ff02945e327 ]] || { echo "G2_FAIL sha file is not the authorized hash"; exit 1; }
sha256sum -c $N.tar.gz.sha256
tar -xzf $N.tar.gz --no-same-owner
cd $N && sha256sum --quiet -c MANIFEST.sha256 && echo "MANIFEST OK ($(wc -l < MANIFEST.sha256) files, $(sha256sum < MANIFEST.sha256 | cut -c1-16))"
cat RELEASE_ID
df -Pm / | awk 'NR==2{print "free_MiB="$4}'; free -m | awk 'NR==2{print "mem_available_MiB="$7}'
echo G2_PASS
