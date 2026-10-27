#!/usr/bin/env bash
# READ-ONLY: was the Router V2 hook reached on DEV turns? (no changes)
set -u
HH=/home/lilith/.hermes-dev
grep -n -i -E 'lilith_router|router|Primary provider auth failed|provider' $HH/logs/gateway.log $HH/logs/agent.log $HH/logs/errors.log 2>/dev/null | cut -c1-210 | tail -12
ls -la $HH/logs/
