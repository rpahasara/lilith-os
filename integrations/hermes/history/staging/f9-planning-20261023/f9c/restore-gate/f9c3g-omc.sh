#!/usr/bin/env bash
# owner-memory-control x2 on the gate tree (/root/omc-f9c3x), 10800 s cap per run (host I/O heavily contended).
set -u
export PYTHONDONTWRITEBYTECODE=1
T=/root/omc-f9c3x; OUT=/root/f9c3x-out
echo "START $(date -Is)"
trap 'echo "EXIT rc=$? $(date -Is)"' EXIT
for run in 1 2; do
  start=$(date +%s)
  echo "run$run begins $(date -Is)"
  (cd $T/services/owner-memory-control && PYTHONPATH=/root/l1deps timeout 10800 python3 -B -m unittest discover -s tests -p "test_*.py" > $OUT/omc-$run.log 2>&1)
  rc=$?
  grep -E "^(FAIL|ERROR): " $OUT/omc-$run.log | sort > $OUT/omc-$run.failures
  echo "owner-memory-control run$run (py3.12): rc=$rc $(( $(date +%s) - start ))s | $(grep -E '^Ran ' $OUT/omc-$run.log) | $(grep -E '^(OK|FAILED)' $OUT/omc-$run.log) | failures=$(wc -l < $OUT/omc-$run.failures)"
done
diff /root/f9c-wsl/omc-base-omc-1.failures $OUT/omc-1.failures && echo "omc failure set identical to b9eb32c baseline"
r=$(cd $T/services/owner-memory-control && PYTHONPATH=/root/l1deps timeout 900 python3 -B -m unittest discover -s tests -p "test_restore_gate_accepted_read.py" 2>&1 | grep -E '^(Ran |OK|FAILED)' | paste -sd' ')
echo "owner-memory-control gated accepted read (py3.12): $r"
