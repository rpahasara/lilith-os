#!/usr/bin/env bash
# Offline Linux Core API test environment (no download, project dependencies unchanged), then the Slice 2 regressions.
#   Core API: CPython 3.11.16 (local F8 build) + /root/coreapi-deps (fastapi 0.116.1 + starlette 0.47.3 copied pure-Python
#             from the Windows env; pydantic 2.13.4/pydantic-core 2.46.4 cp311 + small deps from the local F8 wheelhouse)
#             + /root/l1deps (fido2, rfc8785, cryptography).
#   owner-memory-control: system Python 3.12 + /root/l1deps (as before).
set -u
export PYTHONDONTWRITEBYTECODE=1
PY311=/root/f9b/build/pkg/python/cpython-3.11.16-linux-x86_64-gnu/bin/python3.11
WH=/root/f9b/build/pkg/wheelhouse; D=/root/coreapi-deps; OUT=/root/f9c2-out; rm -rf $OUT; mkdir -p $OUT
for w in pydantic-2.13.4 pydantic_core-2.46.4 anyio-4.12.1 idna-3.18 sniffio-1.3.1 typing_extensions-4.15.0 \
         typing_inspection-0.4.2 annotated_types-0.7.0; do
  f=$(ls $WH/$w-*.whl | head -1); $PY311 -I -c "import zipfile,sys; zipfile.ZipFile(sys.argv[1]).extractall(sys.argv[2])" "$f" $D
done
export PYTHONPATH=$D:/root/l1deps
$PY311 -I -c "pass" 2>/dev/null
$PY311 -c "import fastapi, starlette, pydantic, pydantic_core, fido2, rfc8785, cryptography; from cryptography.hazmat.primitives.asymmetric import ec; print('env:', 'python', __import__('sys').version.split()[0], 'fastapi', fastapi.__version__, 'starlette', starlette.__version__, 'pydantic', pydantic.__version__, 'cryptography', cryptography.__version__)"
for tree in omc-base omc-f9c2; do
  (cd /root/$tree && timeout 1800 $PY311 -B -m unittest discover -s services/core-api/tests -p "test_*.py" > $OUT/$tree-coreapi.log 2>&1)
  echo "$tree core-api (py3.11 env): $(grep -E '^Ran ' $OUT/$tree-coreapi.log) | $(grep -E '^(OK|FAILED)' $OUT/$tree-coreapi.log)"
  grep -E "^(FAIL|ERROR): " $OUT/$tree-coreapi.log | head -5
done
unset PYTHONPATH
for run in 1 2; do
  (cd /root/omc-f9c2/services/owner-memory-control && PYTHONPATH=/root/l1deps timeout 1800 python3 -B -m unittest discover -s tests -p "test_*.py" > $OUT/omc-$run.log 2>&1)
  grep -E "^(FAIL|ERROR): " $OUT/omc-$run.log | sort > $OUT/omc-$run.failures
  echo "omc-f9c2 run$run (py3.12): $(grep -E '^Ran ' $OUT/omc-$run.log) | $(grep -E '^(OK|FAILED)' $OUT/omc-$run.log) | failures=$(wc -l < $OUT/omc-$run.failures)"
done
diff /root/f9c-wsl/omc-base-omc-1.failures $OUT/omc-1.failures && echo "omc failure set identical to b9eb32c baseline"
(cd /root/omc-f9c2/services/core-api/tests && PYTHONPATH=$D:/root/l1deps timeout 900 $PY311 -B -m unittest test_hermes_erasure_owner test_privacy_hermes_owner_v2 > $OUT/slice.log 2>&1)
echo "slice modules (Linux py3.11): $(grep -E '^Ran ' $OUT/slice.log) | $(grep -E '^(OK|FAILED)' $OUT/slice.log)"
(cd /root/omc-f9c2/services/core-api/tests && PYTHONPATH=/root/l1deps timeout 900 python3 -B -m unittest test_hermes_erasure_owner test_privacy_hermes_owner_v2 > $OUT/slice312.log 2>&1)
echo "slice modules (Linux py3.12): $(grep -E '^Ran ' $OUT/slice312.log) | $(grep -E '^(OK|FAILED)' $OUT/slice312.log)"
