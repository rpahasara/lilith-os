#!/usr/bin/env bash
# Compare two observe_host.sh directories. Exit 0 and print F8_OBSERVATION_EQUAL only when every section is
# byte-identical; otherwise print the per-section diff and F8_OBSERVATION_DIFF (a STOP condition).
set -uo pipefail
A=${1:?usage: compare_observations.sh <before> <after>}; B=${2:?}
rc=0
for s in services units sockets custody coreapi accounts; do
  if cmp -s "$A/$s" "$B/$s"; then echo "EQUAL $s"; else echo "DIFF  $s"; diff -u "$A/$s" "$B/$s" | head -40; rc=1; fi
done
[[ $rc -eq 0 ]] && echo "F8_OBSERVATION_EQUAL" || echo "F8_OBSERVATION_DIFF"
exit $rc
