#!/usr/bin/env bash
# MIRROR ONLY (refused on lilith-dev-01): validate the read-only B-4 preflight against an F8r4-installed mirror (the
# DEV state today), and prove it changes nothing: a full metadata+content snapshot of the F8/F9 paths, the Core API
# tree, units and accounts before and after must be identical. Then remove the mirror F8r4 install and the stand-ins.
set -uo pipefail
[[ $(hostname) != lilith-dev-01 ]] || { echo refused; exit 1; }
W=/root/f9ca; T=$W/tracka; P8=/var/tmp/f8/hermes-gateway-dev-f293e72-f8r4; SY=/root/f8r4/synth
B=/var/backups/hermes-gateway-dev; EV=$W/b4-sim-ev; RES=$W/b4-sim.tsv; : > $RES; rm -rf $EV; mkdir -p $EV
rec() { printf '%s\t%s\t%s\n' "$1" "$2" "$3" | tee -a "$RES"; }
MIRROR_SET_UP=0
cleanup() { trap - EXIT
  [[ -x /opt/hermes-gateway-dev/current/bin/rollback.sh ]] && bash /opt/hermes-gateway-dev/current/bin/rollback.sh remove > $EV/cleanup.log 2>&1
  systemctl daemon-reload; bash /root/f8r4/mirror/synthprov.sh down >/dev/null
  [[ $MIRROR_SET_UP == 1 ]] && bash /root/f8r2/mirror/mirror_teardown.sh > $EV/teardown.log 2>&1
  echo "TOTAL: $(grep -cP '\t(PASS|INFO)\t' $RES) ok / $(wc -l < $RES) rows"; }
trap cleanup EXIT
snap() {  # content + metadata of the persistent state the preflight could conceivably touch. Excluded on purpose: the
  # running gateway's own HERMES_HOME runtime (logs, state.db) and /run (F8r4's accepted DR-5 check may leave a sudo
  # timestamp there); both change without the preflight.
  { find /opt/hermes-gateway-dev /etc/hermes-gateway-dev /etc/hermes-provider-gate-dev /var/lib/private/hermes-provider-gate-dev \
         /home/lilith/.hermes/lilith-os-dev /etc/systemd/system /etc/tmpfiles.d $B \
         -xdev \( -type f -printf '%p %U %G %m %s %T@\n' \) -o \( ! -type f -printf '%p %y %U %G %m\n' \) 2>/dev/null | LC_ALL=C sort
    find /home/lilith/.hermes-dev -maxdepth 1 \( -name config.yaml -o -name .env -o -name SOUL.md -o -name lilith_router -o -name plugins \) \
         -printf '%p %U %G %m %s %T@\n' | LC_ALL=C sort
    getent group | LC_ALL=C sort; ls /var/lib | LC_ALL=C sort; } | sha256sum | cut -c1-16; }
if [[ ! -f /etc/systemd/system/lilith-memory-broker.service ]]; then
  bash /root/f8r2/mirror/mirror_setup.sh /root/f8r2/repo /root/f8hd/build/pkg/uv/uv > $EV/mirror-setup.log 2>&1 && MIRROR_SET_UP=1 \
    || { rec mirror-setup FAIL ""; exit 1; }
fi
[[ -d $B ]] && mkdir -p $W/old && mv $B $W/old/backups-$(date +%s)
bash /root/f8r4/mirror/synthprov.sh up >/dev/null
rm -rf /var/tmp/f8 && install -d -m 0700 /var/tmp/f8 && cp /root/f8r4/out/hermes-gateway-dev-f293e72-f8r4.tar.gz* /var/tmp/f8/
(cd /var/tmp/f8 && sha256sum -c --quiet *.sha256 && tar -xzf hermes-gateway-dev-f293e72-f8r4.tar.gz) || { rec G-2 FAIL ""; exit 1; }
systemctl start lilith-memory-broker.service lilith-authority-dev.service lilith-recovery-witness.service lilith-os-api-dev.service; sleep 4
bash $P8/bin/backup_pre_install.sh >/dev/null
F8_SIM=1 bash $P8/bin/install.sh > $EV/install.log 2>&1 || { rec F8R4-install FAIL "$(tail -2 $EV/install.log)"; exit 1; }
bash $P8/bin/provision_console_token.sh >/dev/null
printf '%s\n' "$(cat $SY/synthetic-key)" | script -qec "bash $P8/bin/provision_provider_key.sh" /dev/null > $EV/key.log 2>&1
systemctl start hermes-gateway-dev; for _ in $(seq 1 120); do ss -Hltn 'sport = :9901' | grep -q . && break; sleep 1; done
sleep 5; for _ in $(seq 1 30); do [[ $(systemctl list-jobs --no-legend | wc -l) -eq 0 ]] && break; sleep 2; done
rec F8R4 INFO "installed and running: $(basename "$(readlink -f /opt/hermes-gateway-dev/current)")"
s0=$(snap)
F9C2_B4_SIM=1 bash $T/devops/f9c2-b4-preflight.sh > $EV/b4.log 2>&1; rc=$?
s1=$(snap)
rec B-4-run INFO "rc=$rc $(tail -1 $EV/b4.log); $(grep -c '^CHECK' $EV/b4.log) checks"
grep -E '^CHECK [^ ]+ FAIL' $EV/b4.log | cut -c1-160 | while read -r l; do rec B-4-fail INFO "$l"; done
[[ $s0 == "$s1" ]] && rec B-4-read-only PASS "host snapshot identical before/after ($s0)" || rec B-4-read-only FAIL "$s0 != $s1"
grep -q '^F9C2_B4 PASS' $EV/b4.log && rec B-4 PASS "preflight PASS on the F8r4 state" || rec B-4 FAIL "see b4.log"
for k in f8r4-current f8r4-verify f8r4-release-sha coreapi-f9c-deployed probe-absent-privacy_governance.dev.db no-pending-reload dr5; do
  rec "b4-$k" INFO "$(grep "^CHECK $k " $EV/b4.log | cut -d' ' -f3- | cut -c1-140)"; done
