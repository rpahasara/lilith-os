#!/usr/bin/env bash
# F9c2 B-4: READ-ONLY DEV preflight (lilith-dev-01, root). Changes nothing on the host: only stat/ls/systemctl show/ss/
# df/sha256sum reads, F8r4's own `verify_release.py --full` and `dr5_check.sh` (whose report goes to a private temp dir
# that is removed at exit), and `gate_budget.sh show` (a GET of the gate's /healthz; never reset).
# Output is content-free: states, counts, digests. Every line is CHECK <name> <PASS|FAIL|INFO> <detail>.
#   sudo F9C2_EXPECT_CORE_SHA=<main commit deployed by deploy-dev after the #249 merge> bash f9c2-b4-preflight.sh
# PASS requires the deployed Core API release to be exactly that commit AND its F9-C files to be byte-identical to the
# reviewed PR #249 head 950fc02 (hashes below). Missing, mismatched or unreadable evidence is a FAIL; only an
# all-PASS run prints `F9C2_B4 PASS`.
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
rs=$( [[ -f $R/RELEASE.sha256 && ! -L $R/RELEASE.sha256 ]] && sha256sum < $R/RELEASE.sha256 | cut -c1-64 )
ok f8r4-release-sha '[[ $rs =~ ^[0-9a-f]{64}$ && $rs != e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855 ]]' "${rs:-MISSING} (record as F8R4_RELEASE_SHA in G-0)"
v=$("$R/venv/bin/python" -I -B "$R/bin/verify_release.py" --full 2>&1 | tail -1)
ok f8r4-verify '[[ $v == "F8_VERIFY_PASS full f293e72-f8r4" ]]' "$v"
for u in hermes-gateway-dev hermes-provider-gate-dev; do
  chk "unit-$u" INFO "$(systemctl show $u -p ActiveState,SubState,UnitFileState,NRestarts --value | paste -sd' ')"
done
gb=$(bash $R/bin/gate_budget.sh show 2>/dev/null | tr -d '\n')
chk gate-budget INFO "${gb:0:200} (read-only GET /healthz; never reset)"
ok provider-key-present '[[ -f /etc/hermes-provider-gate-dev/credentials/groq-api-key ]]' \
  "sha_prefix=$(sha256sum < /etc/hermes-provider-gate-dev/credentials/groq-api-key 2>/dev/null | cut -c1-12) (will be quarantined by U-1)"

# 2. Core API: the deployed release must be the expected main commit and carry the reviewed F9-C bytes (PR #249 950fc02)
EXPECT=${F9C2_EXPECT_CORE_SHA:-}
cur=$(readlink -f $APP/current 2>/dev/null)
ok coreapi-expected-sha-given '[[ $EXPECT =~ ^[0-9a-f]{40}$ ]]' "${EXPECT:-UNSET} (the commit deploy-dev deployed)"
ok coreapi-release-is-expected '[[ -n $EXPECT && $(basename "$cur") == "$EXPECT" ]]' "current=$(basename "$cur") bundle=$(cut -c1-16 $cur/.bundle-sha256 2>/dev/null)"
while read -r want rel; do
  have=$( [[ -f $cur/$rel && ! -L $cur/$rel ]] && sha256sum < "$cur/$rel" | cut -c1-64 )
  ok "coreapi-f9c-$(basename $rel)" '[[ $have == "$want" ]]' "${have:0:16}"
done <<'PINS'
a9fc562fcc5572ee3c2204a106369a671817539c96d326640b4671c48d67b57b app.py
280d92360b8cec2440dbec51b7e4451678489eb0e6720b7b0664c889b24c0856 lilith_memory/hermes_erasure_owner.py
64a4d15fe4e3a27a8a3c6e9b9b0bf87158e6d8d0db1e89a8e55872e5419e8817 lilith_memory/hermes_erasure_spool.py
a9b72714ad883a48b56f9ace3a2e0f5837a07e6fc6ea596035c67d13618cfc4b lilith_memory/memory_v2.py
b6aa041c251009967fda8498f2cfe76d260e9af4b15fdc6af7baddc26b573253 lilith_memory/privacy_forget_intent.py
5bdfa8ca1495fb6968dc327fa60e162944ef0a4d4d4544b751bb06bb856d57ea lilith_memory/privacy_forget_runner.py
1b0d94d4fbb64eed8d0d956843b487c133465d9118d5f0843c1b9985dc6bad34 lilith_memory/privacy_governance.py
691260b31642b77cb1205b9dc403774cba38ee86946bef1eeaeb4ad9a67434f7 lilith_memory/privacy_schema_v2.py
PINS
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
for u in $EXISTING; do
  st=$(systemctl show $u -p ActiveState --value 2>/dev/null); d="$(systemctl show $u -p ActiveState,SubState,MainPID,NRestarts --value | paste -sd' ')"
  if [[ $u == lilith-stage3-a2-final.service ]]; then chk "protected-$u" INFO "$d"; else ok "protected-$u" '[[ $st == active ]]' "$d"; fi
done

# 6. DR-5 (F8r4's own pinned check; its report stays in the private temp dir)
d=$(bash $R/bin/dr5_check.sh "$TMP/dr5.txt" 2>&1 | tr '\n' ' ')
ok dr5 '[[ $d == *F8_DR5_EQUAL* ]]' "$(echo "$d" | grep -o 'F8_DR5_[A-Z]*[^ ]*' | head -1)"

# 7. backups present (names and sizes only)
chk backups INFO "$(ls -1 /var/backups/hermes-gateway-dev 2>/dev/null | tr '\n' ' ' | cut -c1-300) total=$(du -sm /var/backups/hermes-gateway-dev 2>/dev/null | cut -f1)MiB"

echo "F9C2_B4 $([[ $fails -eq 0 ]] && echo PASS || echo "FAIL fails=$fails")"
