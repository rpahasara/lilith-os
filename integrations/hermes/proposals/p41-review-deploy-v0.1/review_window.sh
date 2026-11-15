#!/usr/bin/env bash
# PROD install of the P4-1 conversation-date review script (#412). Root on the Contabo PROD host (vmi3753642); ONLY with the owner's explicit GO.
#   sudo bash review_window.sh precheck CANDIDATE        read-only: pins, zone, jobs, blackout
#   sudo bash review_window.sh install CANDIDATE         backup -> atomic swap -> import check; any failure restores
#   sudo bash review_window.sh verify [--dry-run]        read-only: new file in place, dependants import it, jobs ok;
#                                                        --dry-run also builds tonight's review context in memory and
#                                                        prints COUNTS ONLY (reads owner conversation in-process)
#   sudo bash review_window.sh rollback BACKUP_DIR       restore the exact previous file, then import-check it
# One file changes: ~/.hermes/scripts/owner_memory_review.py. No restart: Hermes cron reads it fresh on every run.
# Its dependants import it: owner_memory_snapshot.py (every 10 min) and commitment_sync.py (every minute; that import
# FAILS CLOSED SILENTLY, so a status of "ok" proves nothing; this script imports the module itself).
# Exit: 0 done | 1 refused or failed with the previous file restored and verified | 3 REVIEW_ESCALATE (could not verify).
set -Euo pipefail
umask 077
MODE=${1:-}
PROD_HOST=vmi3753642   # Contabo PROD (was GCP lilith-01 until the 2026-11-14 migration)
H=/home/lilith/.hermes; D=$H/scripts; F=$D/owner_memory_review.py; PY=$H/hermes-agent/venv/bin/python
BKROOT=/var/backups/lilith-review
LIVE_SHA=88bf8f38016295b7bda9fc9b8f050a3ac24ff0ac9f66b6ccddb40f2cdea20963      # #437, live since 2026-11-15 12:32Z
NEW_SHA=47854c322a970e700a5effa3bbe1f9c94e5e0a9ddcb834d7b5525b07cde43aff       # correction-aware review: add or replace (2026-11-15)
declare -A DEP_SHA=([owner_memory_snapshot.py]=99f0fd81d677f8142e569825f0d8659cf845eed468c718216f229181e9721523
                    [commitment_sync.py]=6527dd634292bcf66fb9ce23b422e3d5d8727421b812a1335ad63548cd33f0fa)
refuse() { echo "REVIEW_FAIL $* (nothing changed)" >&2; exit 1; }
escalate() { echo "REVIEW_ESCALATE $*" >&2; exit 3; }
sha() { sha256sum "$1" | cut -d' ' -f1; }
SIM=0
if [[ -n ${REVIEW_SIM:-} ]]; then   # offline rehearsal only: private mount + hostname namespaces, /home on an overlay
  [[ $(readlink /proc/1/ns/mnt) != "$(readlink /proc/self/ns/mnt)" && $(readlink /proc/1/ns/uts) != "$(readlink /proc/self/ns/uts)" \
     && $(stat -f -c %T /home) == overlayfs ]] || refuse "REVIEW_SIM outside a sandbox"
  SIM=1
fi
inject() { [[ $SIM == 1 && ${REVIEW_SIM_FAIL_AT:-} == "$1" ]] && { echo "INJECTED_FAILURE at $1" >&2; return 1; }; return 0; }
as_lilith() { runuser -u lilith -- env -i HOME=/home/lilith HERMES_HOME=$H PATH=/usr/bin:/bin LILITH_OS_API_URL=http://127.0.0.1:8765 "$@"; }

import_check() {   # the module imports and both dependants' imports work; for #412 also its zone (the previous file
                   # has no review_timezone, so a restore is checked by import alone)
  as_lilith "$PY" -I -B -c '
import sys; from pathlib import Path
sys.path.insert(0, sys.argv[1])
import owner_memory_review as R
tz = R.review_timezone(Path(sys.argv[2])) if hasattr(R, "review_timezone") else (None, "n/a")
assert callable(R.owner_ids) and callable(R.owner_discord_dms) and callable(R.snapshot) and callable(R.main)
print("import ok; zone", tz[1], "; review_timezone present", hasattr(R, "review_timezone"))
from owner_memory_review import owner_discord_dms, owner_ids          # commitment_sync.py does exactly this
import runpy; assert callable(runpy.run_path(sys.argv[1] + "/owner_memory_review.py")["snapshot"])   # snapshot does this
' "$D" "$H"
}

precheck() {
  [[ $(id -u) -eq 0 ]] || refuse "not root"
  [[ $(hostname -s) == "$PROD_HOST" ]] || refuse "wrong host"
  local hm=$(date -u +%H:%M); [[ $SIM == 1 && -n ${REVIEW_SIM_CLOCK:-} ]] && hm=$REVIEW_SIM_CLOCK
  local m=$((10#${hm%:*} * 60 + 10#${hm#*:})); (( m >= 16 * 60 && m < 17 * 60 )) && refuse "inside the 16:00-17:00Z review blackout"
  echo "PASS outside the review blackout ($hm)"
  [[ -n ${1:-} && -f $1 && $(sha "$1") == "$NEW_SHA" ]] || refuse "candidate is not the #412 file ($NEW_SHA)"
  echo "PASS candidate = #412 ($NEW_SHA)"
  local cur; cur=$(sha "$F")
  [[ $cur == "$LIVE_SHA" || $cur == "$NEW_SHA" ]] || refuse "live review script is neither the inventoried one nor #412 ($cur)"
  [[ $cur == "$NEW_SHA" && $MODE == install ]] && refuse "already installed"
  [[ $(stat -c '%U:%G %a' "$F") == "lilith:lilith 644" ]] || refuse "live file owner/mode"
  local f; for f in "${!DEP_SHA[@]}"; do [[ $(sha "$D/$f") == "${DEP_SHA[$f]}" ]] || refuse "dependant $f changed"; done
  echo "PASS live file and dependants are the inventoried ones"
  [[ $(as_lilith "$PY" -I -c 'import sys,yaml; print((yaml.safe_load(open(sys.argv[1])) or {}).get("timezone"))' "$H/config.yaml") == Asia/Colombo ]] \
    || refuse "Hermes timezone is not Asia/Colombo"
  echo "PASS Hermes timezone Asia/Colombo"
  as_lilith "$PY" -I -c '
import json, sys, datetime as dt
j = {x["id"]: x for x in json.load(open(sys.argv[1]))["jobs"]}
r, s = j["e161234245f3"], j["f56407e4cef8"]
assert r["enabled"] and r["schedule"]["expr"] == "0 22 * * *" and r.get("script") == "owner_memory_review.py", "review job"
assert s["enabled"] and s.get("last_status") == "ok", "snapshot job"
print("PASS review job 0 22 * * * (", r["next_run_at"], "); snapshot last", s["last_run_at"], "ok")' "$H/cron/jobs.json" \
    || refuse "cron jobs not as inventoried"
  [[ $(systemctl is-active hermes-gateway) == active ]] || refuse "gateway not active"; echo "PASS gateway active"
  echo "REVIEW_PRECHECK_PASS"
}

restore() {   # $1 backup dir
  local bk=$1
  [[ -f $bk/owner_memory_review.py && $(sha "$bk/owner_memory_review.py") == "$LIVE_SHA" ]] || return 1
  install -o lilith -g lilith -m 0644 "$bk/owner_memory_review.py" "$D/.owner_memory_review.py.restore" \
    && mv -f "$D/.owner_memory_review.py.restore" "$F" && [[ $(sha "$F") == "$LIVE_SHA" ]] || return 1
  import_check >/dev/null 2>&1 || return 1
  return 0
}

case $MODE in
  precheck) precheck "${2:-}" ;;
  install)
    CAND=${2:-}; precheck "$CAND"
    BK=$BKROOT/$(date -u +%Y%m%dT%H%M%SZ); install -d -m 0700 "$BKROOT" "$BK" || refuse "backup dir"
    cp -p "$F" "$BK/owner_memory_review.py" && chown root:root "$BK/owner_memory_review.py" && chmod 0600 "$BK/owner_memory_review.py" \
      && [[ $(sha "$BK/owner_memory_review.py") == "$LIVE_SHA" ]] || refuse "backup"
    echo "backup $BK ($LIVE_SHA)"
    fail() { echo "REVIEW_FAIL $1 - restoring $BK" >&2; restore "$BK" || escalate "restore could not be verified; review script state unknown"
             echo "REVIEW_FAIL_RESTORED $1 (previous file $LIVE_SHA back and importing)" >&2; exit 1; }
    inject before_swap || fail "injected before swap"
    install -o lilith -g lilith -m 0644 "$CAND" "$D/.owner_memory_review.py.new" && mv -f "$D/.owner_memory_review.py.new" "$F" \
      || fail "swap"
    [[ $(sha "$F") == "$NEW_SHA" && $(stat -c '%U:%G %a' "$F") == "lilith:lilith 644" ]] || fail "installed file check"
    inject after_swap || fail "injected after swap"
    OUT=$(import_check 2>&1) && [[ $OUT == *"zone Asia/Colombo"*"review_timezone present True"* ]] || fail "import check ($OUT)"
    echo "$OUT"
    echo "REVIEW_INSTALLED $NEW_SHA backup=$BK at $(date -u +%Y-%m-%dT%H:%M:%SZ)"
    ;;
  verify)
    fail=0; v() { if eval "$2"; then echo "PASS $1"; else echo "FAIL $1"; fail=1; fi; }
    v "R1 live file is #412 ($NEW_SHA), lilith 0644" '[[ $(sha "$F") == "$NEW_SHA" && $(stat -c "%U:%G %a" "$F") == "lilith:lilith 644" ]]'
    OUT=$(import_check 2>&1); v "R2 imports; zone Asia/Colombo; dependants import it: $OUT" '[[ $OUT == *"zone Asia/Colombo"* ]]'
    J=$(as_lilith "$PY" -I -c '
import json, sys
j = {x["id"]: x for x in json.load(open(sys.argv[1]))["jobs"]}
for i in ("f56407e4cef8", "5365cfb456d4", "e161234245f3"): print(i, j[i].get("last_run_at"), j[i].get("last_status"), j[i].get("next_run_at"))' "$H/cron/jobs.json")
    v "R3 snapshot / sync / review job status ok: $(echo $J)" '[[ $(grep -c " ok " <<< "$J") -eq 3 ]]'
    if [[ ${2:-} == --dry-run ]]; then   # counts only; snapshot() stubbed so nothing is written
      DR=$(as_lilith "$PY" -I -B -c '
import sys, time; from pathlib import Path
sys.path.insert(0, sys.argv[1]); import owner_memory_review as R
R.snapshot = lambda *a, **k: 0
out = R.main(Path(sys.argv[2]))
conv = out.split("=== OWNER CONVERSATION")[1] if "=== OWNER CONVERSATION" in out else ""
print("silent", out.startswith("NO_NEW"), "| zone_header", "dates in Asia/Colombo" in conv, "| day_markers", conv.count("--- said on "),
      "| owner_lines", conv.count("\nOWNER: "), "| lilith_lines", conv.count("\nLILITH: "), "| repeats_noted", conv.count("[also said on"),
      "| guidance_dates", "Told LILITH on" in out)' "$D" "$H")
      v "R4 dry run (counts only): $DR" '[[ $DR == *"silent True"* || ( $DR == *"zone_header True"* && $DR == *"guidance_dates True"* ) ]]'
    fi
    echo "REVIEW_VERIFY $([[ $fail == 0 ]] && echo PASS || echo FAIL) $(date -u +%Y-%m-%dT%H:%M:%SZ)"; exit $fail ;;
  rollback)
    BK=${2:-}; [[ $(id -u) -eq 0 && $(hostname -s) == "$PROD_HOST" && -n $BK && -f $BK/owner_memory_review.py ]] || refuse "usage / host / backup"
    restore "$BK" || escalate "rollback could not be verified"
    echo "REVIEW_ROLLED_BACK ($LIVE_SHA restored and importing)" ;;
  *) echo "usage: review_window.sh precheck CAND | install CAND | verify [--dry-run] | rollback BACKUP_DIR" >&2; exit 2 ;;
esac
