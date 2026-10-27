#!/usr/bin/env bash
# MIRROR ONLY: build the f9c2 candidate twice and compare (reproducibility).
set -u
[[ $(hostname) != lilith-dev-01 ]] || exit 1
cd /root/f9ca
bash tracka/build/build-f9c.sh > build-f9c2-1.log 2>&1 || { echo BUILD1_FAIL; tail -5 build-f9c2-1.log; exit 1; }
s1=$(cut -c1-64 out-f9c2/hermes-gateway-dev-f293e72-f9c2.tar.gz.sha256)
bash tracka/build/build-f9c.sh > build-f9c2-2.log 2>&1 || { echo BUILD2_FAIL; tail -5 build-f9c2-2.log; exit 1; }
s2=$(cut -c1-64 out-f9c2/hermes-gateway-dev-f293e72-f9c2.tar.gz.sha256)
grep -E '^(manifest=|PATHSET|CHANGED)' build-f9c2-2.log
[[ $s1 == "$s2" ]] && echo "REPRODUCIBLE $s1" || echo "NOT_REPRODUCIBLE $s1 $s2"
