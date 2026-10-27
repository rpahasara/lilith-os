STEP=s1-g2
# Shared header for every Phase B step (pasted into each step by build; kept identical).
set -uo pipefail
[[ $(hostname) == lilith-dev-01 ]] || { echo "WRONG HOST $(hostname)"; exit 1; }
[[ $(id -u) -eq 0 ]] || { echo "NOT ROOT"; exit 1; }
RUN=/var/tmp/f8/f9c2-run; install -d -o root -g root -m 0700 /var/tmp/f8 $RUN
exec > >(tee -a "$RUN/${STEP}.out") 2>&1
CORE=/home/lilith/.hermes/lilith-os-dev; HH=/home/lilith/.hermes-dev; B=/var/backups/hermes-gateway-dev
N=hermes-gateway-dev-f293e72-f9c2; P=/var/tmp/f8/$N; R=/opt/hermes-gateway-dev/current
PKG_SHA=4b0b0110dde1cccd585203ea9a92cfe8b8cbe31d8e1a6e4edb461ba2c09c3ba5; MANIFEST_SHA=c78a8bd2d00c80dc3c3cca5f2dac3cd55a748405412730e48f68e0b3e9ff46dd
CORE_SHA=3f6b909f8b4c73a132c49626da585ee998cddda1; F8R4_SHA=7343b245f62ecf3ee70be860a55e550c4a0e14f9192ac21c3ed8f373cc8b2bd9
LED=/var/lib/private/hermes-provider-gate-dev/ledger.log; INTENT=/var/lib/hermes-forget/intent/first-interaction.intent
MARK=/var/lib/hermes-forget/in-progress; CAN=F9C2-DEV-CANARY
die() { echo "STEP_FAIL ${STEP} $*"; exit 1; }
ok() { if eval "$2"; then echo "OK $1 ${3:-}"; else die "$1 ${3:-}"; fi; }
pids() { for u in lilith-memory-broker.service lilith-authority-dev.service lilith-recovery-witness.service; do
  printf '%s=%s ' "${u%%.service}" "$(systemctl show $u -p MainPID,NRestarts,ActiveState --value | paste -sd/)"; done; echo; }
parity() { ok protected-parity '[[ $(pids) == "lilith-memory-broker=3411/0/active lilith-authority-dev=128648/0/active lilith-recovery-witness=127192/0/active " ]]' "$(pids)"; }
dr5() { local d; d=$(bash ${1:-$R}/bin/dr5_check.sh "$RUN/dr5-${STEP}.txt" 2>&1 | tr '\n' ' '); ok dr5 '[[ $d == *F8_DR5_EQUAL* ]]' "$(echo $d | grep -o 'F8_DR5_[A-Z]*' | head -1)"; }
echo "=== ${STEP} $(date -u +%Y-%m-%dT%H:%M:%SZ) boot=$(cut -c1-8 /proc/sys/kernel/random/boot_id)"
# S1 (G-2): move the uploaded f9c2 package into root-only /var/tmp/f8 and verify tarball, MANIFEST, RELEASE_ID.
ok f8-dir '[[ $(stat -c "%U %a" /var/tmp/f8) == "root 700" ]]'
ok not-present '[[ ! -e $P && ! -e /var/tmp/f8/$N.tar.gz ]]'
mv /var/tmp/$N.tar.gz /var/tmp/$N.tar.gz.sha256 /var/tmp/f8/ || die mv
chown root:root /var/tmp/f8/$N.tar.gz*; chmod 0600 /var/tmp/f8/$N.tar.gz*
cd /var/tmp/f8
ok sha-file '[[ $(cut -c1-64 $N.tar.gz.sha256) == $PKG_SHA ]]'
ok tarball '[[ $(sha256sum < $N.tar.gz | cut -c1-64) == $PKG_SHA ]]' "$PKG_SHA"
tar -xzf $N.tar.gz --no-same-owner || die tar
cd $P && sha256sum --quiet -c MANIFEST.sha256 || die MANIFEST
ok manifest '[[ $(sha256sum < MANIFEST.sha256 | cut -c1-64) == $MANIFEST_SHA ]]' "$(wc -l < MANIFEST.sha256) files $MANIFEST_SHA"
ok release-id '[[ $(cat RELEASE_ID) == f293e72-f9c2 ]]'
ok drill-tool '[[ -f bin/f9c_dev_drill.py && -f bin/install_f9c.sh && -f bin/preserve_f8r4.sh && -f bin/restore_f8r4.sh ]]'
echo "S1_PASS"
