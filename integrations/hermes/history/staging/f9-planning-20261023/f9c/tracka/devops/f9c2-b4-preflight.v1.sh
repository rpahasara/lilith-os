#!/usr/bin/env bash
# F9c2 B-4: READ-ONLY DEV preflight (lilith-dev-01, root). Changes nothing on the host: only stat/ls/systemctl show/ss/
# df/sha256sum reads, F8r4's own `verify_release.py --full` and `dr5_check.sh` (whose report goes to a private temp dir
# that is removed at exit), and `gate_budget.sh show` (a GET of the gate's /healthz; never reset).
# Output is content-free: states, counts, digests. Every line is CHECK <name> <PASS|FAIL|INFO> <detail>.
#   sudo bash f9c2-b4-preflight.sh            (from any directory; nothing is installed or copied)
set -uo pipefail
[[ $(id -u) -eq 0 ]] || { echo "CHECK root FAIL not root"; exit 1; }
[[ ${F9C2_B4_SIM:-} == 1 && $(hostname) != lilith-dev-01 ]] || [[ $(hostname) == lilith-dev-01 ]] \
  || { echo "CHECK host FAIL $(hostname)"; exit 1; }
TMP=$(mktemp -d /tmp/f9c2-b4.XXXXXX); trap 'rm -rf "$TMP"' EXIT
fails=0
chk() { echo "CHECK $1 $2 ${3:-}"; [[ $2 == FAIL ]] && fails=$((fails + 1)); return 0; }
ok() { if eval "$2"; then chk "$1" PASS "${3:-}"; else chk "$1" FAIL "${3:-}"; fi; }
APP=/home/lilith/.hermes/lilith-os-dev; DATA=$APP/data; R=/opt/hermes-gateway-dev/current
EXISTING="lilith-os-api-dev.service lilith-memory-broker.service lilith-memory-broker.socket lilith-authority-dev.service lilith-authority-dev.socket lilith-recovery-witness.service lilith-recovery-witness-owner.socket lilith-recovery-witness-signer.socket lilith-stage3-a2-final.service"

chk host PASS "$(hostname) $(date -u +%Y-%m-%dT%H:%M:%SZ) boot=$(cut -c1-8 /proc/sys/kernel/random/boot_id)"

# 1. installed F8r4 (the rollback baseline) and its integrity
rel=$(basename "$(readlink -f $R 2>/dev/null)")
ok f8r4-current '[[ $rel == f293e72-f8r4 ]]' "current=$rel"
chk f8r4-release-sha INFO "$(sha256sum < $R/RELEASE.sha256 2>/dev/null | cut -c1-64) (record as F8R4_RELEASE_SHA in G-0)"
v=$("$R/venv/bin/python" -I -B "$R/bin/verify_release.py" --full 2>&1 | tail -1)
ok f8r4-verify '[[ $v == "F8_VERIFY_PASS full f293e72-f8r4" ]]' "$v"
for u in hermes-gateway-dev hermes-provider-gate-dev; do
  chk "unit-$u" INFO "$(systemctl show $u -p ActiveState,SubState,UnitFileState,NRestarts --value | paste -sd' ')"
done
chk gate-budget INFO "$(bash $R/bin/gate_budget.sh show 2>/dev/null | tr -d '\n' | cut -c1-160) (read-only; never reset)"
ok provider-key-present '[[ -f /etc/hermes-provider-gate-dev/credentials/groq-api-key ]]' \
  "sha_prefix=$(sha256sum < /etc/hermes-provider-gate-dev/credentials/groq-api-key 2>/dev/null | cut -c1-12) (will be quarantined by U-1)"

# 2. Core API (deployed release; F9-C must be deployed before install_f9c)
cur=$(readlink -f $APP/current 2>/dev/null)
chk coreapi-release INFO "current=$(basename "$cur") bundle=$(cat $cur/.bundle-sha256 2>/dev/null | cut -c1-16) owner=$(stat -c %U $cur/lilith_memory 2>/dev/null)"
f9c=yes; for m in privacy_forget_intent.py hermes_erasure_spool.py hermes_erasure_owner.py privacy_forget_runner.py privacy_schema_v2.py; do
  [[ -f $cur/lilith_memory/$m ]] || f9c=no; done
grep -q "def identity_forget_completed" "$cur/lilith_memory/privacy_governance.py" 2>/dev/null || f9c=no
chk coreapi-f9c-deployed INFO "$f9c (must be yes before install_f9c: PR #249 merged and deployed)"
ok coreapi-active '[[ $(systemctl is-active lilith-os-api-dev) == active ]]' "pid=$(systemctl show lilith-os-api-dev -p MainPID --value)"
ok coreapi-venv '[[ -x $APP/api-venv/bin/python ]]' "the drill tool runs with this interpreter"

# 3. the deploy-time durability probe's stores must be absent (its prepare refuses otherwise)
for p in $DATA/privacy_governance.dev.db $DATA/cognitive_memory.dev.db $DATA/canonical-durability-probe; do
  ok "probe-absent-$(basename $p)" '[[ ! -e $p && ! -L $p ]]'
done
chk capture-db INFO "$([[ -e $DATA/conversation-evidence.db ]] && echo present || echo absent) (relay capture; L18_V2 is given this path)"

# 4. no F9-C leftovers
for p in /var/lib/hermes-forget /etc/hermes-forget /run/hermes-forget $APP/f9-drill /etc/tmpfiles.d/hermes-forget.conf \
         /etc/systemd/system/hermes-gateway-dev.service.d/50-forget.conf; do ok "absent-$(echo $p | tr / _)" '[[ ! -e $p ]]'; done
ok no-forget-units '[[ -z $(ls /etc/systemd/system | grep hermes-forget) ]]'
ok no-lilith-forget-group '! getent group lilith-forget >/dev/null'

# 5. systemd and host hygiene (C-3)
pend=$(systemctl list-units --all --no-legend --plain | awk '{print $1}' | while read -r u; do [[ $(systemctl show "$u" -p NeedDaemonReload --value 2>/dev/null) == yes ]] && echo "$u"; done | wc -l)
ok no-pending-reload '[[ $pend -eq 0 ]]' "units_needing_reload=$pend"
ok no-queued-jobs '[[ $(systemctl list-jobs --no-legend | wc -l) -eq 0 ]]'
ok no-dpkg-lock '[[ -z $(find /proc/[0-9]*/fd -lname "/var/lib/dpkg/lock*" 2>/dev/null) ]]'
for t in apt-daily.timer apt-daily-upgrade.timer; do chk "next-$t" INFO "$(systemctl show $t -p NextElapseUSecRealtime --value)"; done
for m in /opt /var /home; do a=$(df -Pm $m | awk 'NR==2{print $4}'); ok "free-$m" '[[ $a -gt 2048 ]]' "${a}MiB"; done
ok tools '[[ -x $(command -v python3) && -x $(command -v systemd-analyze) && -x $(command -v ss) ]]'
for u in $EXISTING; do chk "protected-$u" INFO "$(systemctl show $u -p ActiveState,SubState,MainPID,NRestarts --value | paste -sd' ')"; done

# 6. DR-5 (F8r4's own pinned check; its report stays in the private temp dir)
d=$(bash $R/bin/dr5_check.sh "$TMP/dr5.txt" 2>&1 | tr '\n' ' ')
ok dr5 '[[ $d == *F8_DR5_EQUAL* ]]' "$(echo "$d" | grep -o 'F8_DR5_[A-Z]*[^ ]*' | head -1)"

# 7. backups present (names and sizes only)
chk backups INFO "$(ls -1 /var/backups/hermes-gateway-dev 2>/dev/null | tr '\n' ' ' | cut -c1-300) total=$(du -sm /var/backups/hermes-gateway-dev 2>/dev/null | cut -f1)MiB"

echo "F9C2_B4 $([[ $fails -eq 0 ]] && echo PASS || echo "FAIL fails=$fails")"
