#!/usr/bin/env bash
# Build each Phase B step script: STEP=<name> + common.inc + <name>.body (LF only).
set -euo pipefail
cd "$(dirname "$0")"
for b in *.body; do
  s=${b%.body}
  { printf 'STEP=%s\n' "$s"; cat common.inc; cat "$b"; } | sed 's/\r$//' > "$s.sh"
  bash -n "$s.sh"
  printf '%s %s\n' "$(sha256sum < "$s.sh" | cut -c1-16)" "$s.sh"
done
