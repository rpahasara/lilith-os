#!/usr/bin/env bash
# READ-ONLY: print the exact base snippets the F9-A patch will change.
set -u
P=/root/f8r4/build/pkg
echo "== run.py first-contact block"; grep -n "First-message onboarding" $P/src/gateway/run.py
n=$(grep -n "First-message onboarding" $P/src/gateway/run.py | cut -d: -f1); sed -n "$((n)),$((n+5))p" $P/src/gateway/run.py | cat -A | cut -c1-140
echo "== source var in scope"; sed -n "$((n-400)),$((n))p" $P/src/gateway/run.py | grep -n "source\b\|source =" | tail -5
echo "== test_f7 preview test"; sed -n 270,300p $P/tests/test_f7_offline.py
echo "== config.yaml lines 55-70"; sed -n 55,70p $P/home/config.yaml
echo "== SOUL / personality refs in package"; grep -rln "SOUL.md" $P/home $P/bin 2>/dev/null | head; sha256sum $P/src/hermes_cli/personality.py
echo "== hashes"; sha256sum $P/src/gateway/run.py $P/home/lilith_router/gateway_integration.py $P/home/config.yaml $P/tests/test_f7_offline.py
