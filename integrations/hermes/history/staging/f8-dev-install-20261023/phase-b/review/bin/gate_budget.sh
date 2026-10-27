#!/usr/bin/env bash
# F8r3 provider-gate budget (root).  gate_budget.sh show  |  gate_budget.sh reset --owner-approved
# The acceptance budget (gate.json budget_requests, 5) never resets by itself; a reset is an owner decision.
set -Eeuo pipefail
ST=/var/lib/private/hermes-provider-gate-dev/state.json
case "${1:-show}" in
  show) curl -s -m 5 http://127.0.0.1:9911/healthz; echo ;;
  reset)
    [[ ${2:-} == --owner-approved ]] || { echo "refused: reset needs --owner-approved" >&2; exit 2; }
    # The gate re-reads its state file on every request: no restart (restarts count against its StartLimitBurst).
    [[ -f ${ST} ]] && python3 -I -c 'import json,sys;p=sys.argv[1];d=json.load(open(p));d["budget_used"]=0;json.dump(d,open(p,"w"))' "${ST}"
    curl -s -m 5 http://127.0.0.1:9911/healthz; echo ;;
  *) echo "usage: gate_budget.sh show|reset --owner-approved" >&2; exit 2 ;;
esac
