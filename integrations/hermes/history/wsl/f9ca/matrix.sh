#!/usr/bin/env bash
set -u
export PYTHONDONTWRITEBYTECODE=1
export F9C_CORE_API=/root/f9ca/repo/services/core-api
export F9C_EXECUTOR_PKG=/root/f9ca/tracka/pkgfiles
export F9C_HERMES_SRC=/root/f9b/build/pkg/src
cd /root/f9ca/tracka/tests
PYTHONPATH=/root/l1deps:$F9C_CORE_API timeout 7200 python3 -B -m unittest -v "${@:-test_f9c_executor_matrix}" 2>&1
