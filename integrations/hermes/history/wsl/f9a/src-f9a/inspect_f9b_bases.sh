#!/usr/bin/env bash
# READ-ONLY: base hashes and anchor checks for the F9-B patch.
set -u
F8=/root/f8r4/build/pkg; O=/root/f9a/overrides
sha256sum $O/src/gateway/run.py $F8/src/agent/turn_context.py $F8/src/agent/agent_runtime_helpers.py $F8/profiles/operate/config.yaml
echo "== operate memory block"; grep -n -A4 '^memory:' $F8/profiles/operate/config.yaml
echo "== timestamp anchor count"; grep -c 'timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")' $F8/src/agent/agent_runtime_helpers.py
echo "== def anchor count"; grep -c '^def dump_api_request_debug(' $F8/src/agent/agent_runtime_helpers.py
echo "== imports at top of agent_runtime_helpers"; sed -n 1,40p $F8/src/agent/agent_runtime_helpers.py | grep -n 'import'
