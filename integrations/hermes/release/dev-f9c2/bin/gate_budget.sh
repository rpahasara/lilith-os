#!/usr/bin/env bash
# F8r4 provider-gate budget (root).  gate_budget.sh show  |  gate_budget.sh reset --owner-approved "<note>"
# The budget is the gate's append-only ledger (R lines after the last RESET). It never resets by itself; a reset is
# an explicit owner decision recorded as a RESET line (the gate reads the ledger on every request: no restart).
set -Eeuo pipefail
L=/var/lib/private/hermes-provider-gate-dev/ledger.log
case "${1:-show}" in
  show) curl -s -m 5 http://127.0.0.1:9911/healthz; echo ;;
  reset)
    [[ ${2:-} == --owner-approved && -n ${3:-} ]] || { echo "refused: reset needs --owner-approved \"<note>\"" >&2; exit 2; }
    [[ -f ${L} ]] || { echo "no ledger" >&2; exit 1; }
    note=$(printf '%s' "$3" | tr -c 'A-Za-z0-9._-' '-' | cut -c1-60)
    printf 'RESET %s %s\n' "$(date -u +%Y-%m-%dT%H:%M:%S+00:00)" "${note}" >> "${L}"; sync -f "${L}"
    curl -s -m 5 http://127.0.0.1:9911/healthz; echo ;;
  *) echo "usage: gate_budget.sh show | reset --owner-approved \"<note>\"" >&2; exit 2 ;;
esac
