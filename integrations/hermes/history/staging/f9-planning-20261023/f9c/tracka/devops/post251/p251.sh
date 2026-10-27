# Post-PR-#251 F9c2 preservation: STRICTLY READ-ONLY (no tee, no files written, no service calls that mutate).
set -uo pipefail
[[ $(hostname) == lilith-dev-01 ]] || { echo "WRONG HOST"; exit 1; }
[[ $(id -u) -eq 0 ]] || { echo "NOT ROOT"; exit 1; }
CORE=/home/lilith/.hermes/lilith-os-dev; HH=/home/lilith/.hermes-dev; B=/var/backups/hermes-gateway-dev; R=/opt/hermes-gateway-dev/current
LED=/var/lib/private/hermes-provider-gate-dev/ledger.log; FG=/var/lib/hermes-forget
echo "=== p251 $(date -u +%FT%TZ) boot=$(cut -c1-8 /proc/sys/kernel/random/boot_id)"
svc() { printf '%s ' "$1"; systemctl show "$1" -p ActiveState,SubState,MainPID,NRestarts,InvocationID,ExecMainStartTimestamp --value | paste -sd'|'; }
echo "--- 1 deployment"
echo "core current=$(basename "$(readlink -f $CORE/current)")"
svc lilith-os-api-dev
echo "core health=$(curl -s -m 5 http://127.0.0.1:8765/health)"
P=$(systemctl show lilith-os-api-dev -p MainPID --value); G=$(getent group lilith-forget | cut -d: -f3)
echo "core lilith-forget group in process: $(grep -qw "$G" <(grep ^Groups: /proc/$P/status) && echo yes || echo NO)"
svc hermes-gateway-dev; svc hermes-provider-gate-dev
echo "listeners: $(ss -Hltn | awk '{print $4}' | grep -E ':(9901|9911|8765)$' | sort | paste -sd' ')"
echo "gateway release=$(basename "$(readlink -f $R)")"
echo "--- 2 forget"
echo "receipts: $(find $FG/receipts -type f -printf '%f %u:%g %m\n' 2>/dev/null)"
sha256sum $FG/receipts/*.json $FG/epochs/epochs.log $B/FORGET-TOMBSTONES/*.json 2>&1 | sed 's#  .*/#  #'
echo "epochs lines=$(wc -l < $FG/epochs/epochs.log)"
echo "intent files=$(ls -A $FG/intent 2>/dev/null | wc -l) marker=$([[ -e $FG/in-progress ]] && echo present || echo absent)"
for u in hermes-forget.path hermes-forget-hold.path hermes-forget-reconcile.timer; do echo "$u $(systemctl is-active $u)"; done
ro() {  # <db> <sql...>: immutable read only if no WAL is present (SQLite then creates/touches no file)
  local db=$1; shift
  if [[ -s "$db-wal" ]]; then echo "WAL_PRESENT(not opened)"; return; fi
  python3 - "$db" "$@" <<'PY'
import sqlite3, sys
c = sqlite3.connect("file:" + sys.argv[1] + "?mode=ro&immutable=1", uri=True)
print(" ".join(str(c.execute(q).fetchone()[0]) for q in sys.argv[2:]))
PY
}
DR=$CORE/f9-drill
ls -la --time-style=+ $DR | awk 'NR>1{print "  drill", $1, $3, $5, $NF}'
echo "privacy receipt/request/hold/auth/suppression: $(ro $DR/privacy_governance.f9drill.db 'select count(*) from privacy_completion_receipt' 'select count(*) from privacy_forget_request' 'select count(*) from privacy_hold' 'select count(*) from privacy_erasure_authorization' 'select count(*) from privacy_restore_suppression_manifest')"
echo "approval evidence (nonce f9c-dev-drill.owner-g0-f9c2-drill-20261025) ref/consumed: $(ro $DR/cognitive_memory.f9drill.db "select count(*) from actor_evidence_ref where nonce='f9c-dev-drill.owner-g0-f9c2-drill-20261025'" "select count(*) from actor_evidence_consumption c join actor_evidence_ref r on r.actor_evidence_ref_id=c.actor_evidence_ref_id where r.nonce='f9c-dev-drill.owner-g0-f9c2-drill-20261025'")"
echo "hermes state.db sessions/messages: $(ro $HH/state.db 'select count(*) from sessions' 'select count(*) from messages')"
echo "hermes state.db files: $(ls -la --time-style=+%FT%T $HH/state.db* 2>/dev/null | awk '{print $NF":"$5}' | paste -sd' ')"
echo "canary hits (files): $(grep -rlaF F9C2-DEV-CANARY $HH $B $FG 2>/dev/null | wc -l)  namespace journal: $(journalctl --namespace=hermes-gateway-dev -o cat --no-pager 2>/dev/null | grep -c F9C2-DEV-CANARY)"
echo "--- 3 provider"
echo "ledger sha=$(sha256sum < $LED | cut -c1-64) lines=$(wc -l < $LED) resets=$(grep -c RESET $LED)"
echo "gate journal FORWARDED=$(journalctl --namespace=hermes-gateway-dev -u hermes-provider-gate-dev -o cat --no-pager 2>/dev/null | grep -c '"decision": "FORWARDED"')"
K=/etc/hermes-provider-gate-dev/credentials/groq-api-key; echo "provider key file: $([[ -e $K ]] && stat -c '%U:%G %a size=%s' $K || echo ABSENT)"
echo "--- 4 protected"
for u in lilith-memory-broker lilith-authority-dev lilith-recovery-witness; do svc $u; done
echo "--- 6 track b side effects"
echo "authority current=$(basename "$(readlink -f /opt/lilith-authority-dev/current)") releases=$(ls /opt/lilith-authority-dev/releases | paste -sd,)"
echo "privacy_anchor.py in current: $([[ -e /opt/lilith-authority-dev/current/lilith_recovery_witness/privacy_anchor.py ]] && echo PRESENT || echo absent)"
echo "witness unit sha=$(sha256sum < /etc/systemd/system/lilith-recovery-witness.service | cut -c1-64)"
echo "witness tmpfiles sha=$(sha256sum < /etc/tmpfiles.d/lilith-recovery-witness.conf 2>/dev/null | cut -c1-64)"
echo "witness credentials: $(ls /etc/lilith-recovery-witness/credentials | paste -sd,)"
echo "anchor state dir: $([[ -e /var/lib/lilith-privacy-anchor ]] && echo PRESENT || echo absent)  freshness marker: $([[ -e /run/lilith-privacy-fresh ]] && echo PRESENT || echo absent)"
echo "witness DropInPaths=$(systemctl show lilith-recovery-witness -p DropInPaths --value)"
echo "P251_DONE"
