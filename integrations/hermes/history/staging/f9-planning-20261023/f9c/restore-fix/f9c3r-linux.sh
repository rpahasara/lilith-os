#!/usr/bin/env bash
# F9-C restore-suppression fix Linux regressions (from the Slice 3 script) (offline; project dependencies unchanged). Same environments as Slice 2:
#   Core API: CPython 3.11.16 (local F8 build) + /root/coreapi-deps (fastapi 0.116.1, starlette 0.47.3, pydantic 2.13.4
#             cp311 + small deps; prepared in Slice 2, nothing downloaded) + /root/l1deps.
#   test_owner_proof and owner-memory-control: system Python 3.12 + /root/l1deps (cryptography is cp312-built).
set -u
export PYTHONDONTWRITEBYTECODE=1
PY311=/root/f9b/build/pkg/python/cpython-3.11.16-linux-x86_64-gnu/bin/python3.11
D=/root/coreapi-deps; T=/root/omc-f9c3r; OUT=/root/f9c3r-out; rm -rf $OUT; mkdir -p $OUT
PYTHONPATH=$D:/root/l1deps $PY311 -c "import sys, fastapi, starlette, pydantic; print('env: python', sys.version.split()[0], 'fastapi', fastapi.__version__, 'starlette', starlette.__version__, 'pydantic', pydantic.__version__)" 2>&1
(cd $T && PYTHONPATH=$D:/root/l1deps timeout 1800 $PY311 -B -m unittest discover -s services/core-api/tests -p "test_*.py" > $OUT/coreapi.log 2>&1)
echo "core-api discover (py3.11 env): $(grep -E '^Ran ' $OUT/coreapi.log) | $(grep -E '^(OK|FAILED)' $OUT/coreapi.log)"
grep -E "^(FAIL|ERROR): " $OUT/coreapi.log
r=$(cd $T/services/core-api/tests && PYTHONPATH=/root/l1deps timeout 900 python3 -B -m unittest test_owner_proof 2>&1 | grep -E '^(Ran |OK|FAILED)' | paste -sd' ')
echo "test_owner_proof (py3.12 + l1deps): $r"
for py in "$PY311" python3; do
  r=$(cd $T/services/core-api/tests && PYTHONPATH=$D:/root/l1deps timeout 900 $py -B -m unittest test_privacy_restore_suppression test_privacy_restore_capture test_privacy_forget_capture test_privacy_forget_lineage test_privacy_forget_runner test_hermes_erasure_owner test_privacy_hermes_owner_v2 2>&1 | grep -E '^(Ran |OK|FAILED)' | paste -sd' ')
  echo "restore fix + slice 1-3 + F4/F1 modules ($($py -c 'import sys; print(sys.version.split()[0])')): $r"
done
for run in 1 2; do
  (cd $T/services/owner-memory-control && PYTHONPATH=/root/l1deps timeout 900 python3 -B -m unittest discover -s tests -p "test_*.py" > $OUT/omc-$run.log 2>&1)
  grep -E "^(FAIL|ERROR): " $OUT/omc-$run.log | sort > $OUT/omc-$run.failures
  echo "owner-memory-control run$run (py3.12): $(grep -E '^Ran ' $OUT/omc-$run.log) | $(grep -E '^(OK|FAILED)' $OUT/omc-$run.log) | failures=$(wc -l < $OUT/omc-$run.failures)"
done
diff /root/f9c-wsl/omc-base-omc-1.failures $OUT/omc-1.failures && echo "omc failure set identical to b9eb32c baseline"
