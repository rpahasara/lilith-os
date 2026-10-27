#!/usr/bin/env bash
# Why test_owner_proof cannot import under the py3.11 env, and its result under py3.12 (+l1deps) on both trees.
set -u
export PYTHONDONTWRITEBYTECODE=1
grep -A12 "^ERROR: test_owner_proof" /root/f9c2-out/omc-f9c2-coreapi.log | grep -E "Error|import" | tail -3
for tree in omc-base omc-f9c2; do
  r=$(cd /root/$tree/services/core-api/tests && PYTHONPATH=/root/l1deps timeout 900 python3 -B -m unittest test_owner_proof 2>&1 | grep -E '^(Ran |OK|FAILED)' | paste -sd' ')
  echo "$tree test_owner_proof (py3.12 + l1deps): $r"
done
grep -E "^Ran |^OK|^FAILED" /root/f9c2-out/omc-f9c2-coreapi.log
for m in test_conversation_evidence test_goal_executive test_memory_projection_epistemic test_privacy_forget_capture; do
  r=$(cd /root/omc-f9c2/services/core-api/tests && PYTHONPATH=/root/coreapi-deps:/root/l1deps timeout 600 /root/f9b/build/pkg/python/cpython-3.11.16-linux-x86_64-gnu/bin/python3.11 -B -m unittest $m 2>&1 | grep -E '^(Ran |OK|FAILED)' | paste -sd' ')
  echo "$m (fastapi env, f9c2): $r"
done
