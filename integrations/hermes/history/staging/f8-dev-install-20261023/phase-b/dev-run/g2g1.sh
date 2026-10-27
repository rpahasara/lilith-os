#!/usr/bin/env bash
# G-2 (verify transferred f8r4 package into /var/tmp/f8) + G-1 (upgrade-pre backup, F8r2 running) + G-1b (DR-5, f8r4 tooling).
set -uo pipefail
[[ $(hostname) == lilith-dev-01 ]] || { echo "WRONG HOST"; exit 1; }
N=hermes-gateway-dev-f293e72-f8r4; H=16c7417dc97a11ba6cf65fe44ef639e255bff22257f65d5f9bcefaab1af9d41a
B=/var/backups/hermes-gateway-dev; P=/var/tmp/f8/$N
[[ -d /var/tmp/f8 && $(stat -c '%U %a' /var/tmp/f8) == "root 700" ]] || { echo "G2_FAIL /var/tmp/f8 not root 0700"; exit 1; }
[[ ! -e $P && ! -e /var/tmp/f8/$N.tar.gz ]] || { echo "G2_FAIL f8r4 already present in /var/tmp/f8"; exit 1; }
mv /var/tmp/$N.tar.gz /var/tmp/$N.tar.gz.sha256 /var/tmp/f8/ || { echo G2_FAIL mv; exit 1; }
chown root:root /var/tmp/f8/$N.tar.gz*; chmod 0600 /var/tmp/f8/$N.tar.gz*
cd /var/tmp/f8
[[ $(cut -c1-64 $N.tar.gz.sha256) == $H ]] || { echo "G2_FAIL sha file is not the authorized hash"; exit 1; }
[[ $(sha256sum < $N.tar.gz | cut -c1-64) == $H ]] || { echo "G2_FAIL tarball hash"; exit 1; }
sha256sum -c $N.tar.gz.sha256 || { echo G2_FAIL; exit 1; }
tar -xzf $N.tar.gz --no-same-owner || { echo G2_FAIL tar; exit 1; }
cd $N && sha256sum --quiet -c MANIFEST.sha256 || { echo "G2_FAIL MANIFEST"; exit 1; }
echo "MANIFEST OK ($(wc -l < MANIFEST.sha256) files, $(sha256sum < MANIFEST.sha256 | cut -c1-64))"
echo "RELEASE_ID=$(cat RELEASE_ID)"
echo "gate.json=$(sha256sum < gate/gate.json | cut -c1-16)"
df -Pm / | awk 'NR==2{print "free_MiB="$4}'; free -m | awk 'NR==2{print "mem_available_MiB="$7}'
echo G2_PASS
echo "== G-1"
bash $P/bin/backup_pre_install.sh || { echo G1_FAIL; exit 1; }
G1=$(ls -d $B/upgrade-pre-* | tail -1); echo "G1=$G1"
cat $G1/observation/SECTIONS.sha256
awk '{print $1, $3, $4, $5, $6}' $G1/observation/services
echo "== G-1b"
bash $P/bin/dr5_check.sh $B/dr5-f8r4-pre.txt && echo G1_PASS || echo G1B_FAIL
