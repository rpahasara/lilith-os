#!/usr/bin/env bash
# READ-ONLY: locate F9-A change points in the built F8r4 package tree.
set -u
P=/root/f8r4/build/pkg; IN=/root/f8hd/in
echo "== overlay files (F7/PROD patched)"; sed 's/^[0-9a-f]* \*\?//' $IN/hermes-patched.sha256 | head -40
echo "== run.py in overlay?"; grep -c 'gateway/run.py' $IN/hermes-patched.sha256
echo "== home payload files"; find $P/home -type f | sort
echo "== preview writers"; grep -rn -i "preview" $P/home/lilith_router $P/home/plugins --include=*.py | head -40
echo "== sidecar / api_content consumers in lilith_os adapter"; grep -n -i "sidecar\|api_content\|platform" $P/home/plugins/lilith_os/adapter.py | head -20
echo "== F7 tests referencing preview / decisions"; grep -n -i "preview\|decision" $IN/test_f7_offline.py | head -30
