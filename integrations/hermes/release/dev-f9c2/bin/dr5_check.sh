#!/usr/bin/env bash
# C-5: run the pinned DR-5 proof as the routine deployer identity and compare its WHOLE output with the expected
# block. Read-only (stat/test access checks, `sudo -n -l` policy queries, pkcheck queries); run as root:
#   dr5_check.sh <outfile>
# PASS requires all of: script sha256 = PIN, run as AB_DEPLOYER (uid != 0), exit 0, final lines
# "PR1_AUTHORITY_BOUNDARY maturity=P1A-9" + "AUTHORITY_BOUNDARY_PROOF=PASS maturity=L1c.3", 0 FAIL, 0 ALLOWED, and the
# output byte-identical to the expected DEV block. A generic PASS line alone is never sufficient.
set -uo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUT=${1:?usage: dr5_check.sh <outfile>}
SCRIPT="${HERE}/dr5/deployer_authority_boundary_proof.sh"
EXPECTED="${HERE}/dr5/expected-dev-block-b9eb32c.txt"
PIN=9b569f9bee8f07f0bf13ec1d20e2607d9e01c601a2e94a2988320e5bc4160f43
EXPECTED_PIN=7fe21378bb97f57aed3a6c60f6fc216e08d646f9da42d9c35feb7509f5468f1c
DEPLOYER=sa_112096412008414111981
fail() { echo "F8_DR5_FAIL $*"; exit 1; }
[[ $(sha256sum < "${SCRIPT}" | cut -d' ' -f1) == "${PIN}" ]] || fail "SCRIPT_PIN_MISMATCH"
[[ $(sha256sum < "${EXPECTED}" | cut -d' ' -f1) == "${EXPECTED_PIN}" ]] || fail "EXPECTED_BLOCK_PIN_MISMATCH"
id "${DEPLOYER}" >/dev/null 2>&1 || fail "DEPLOYER_ACCOUNT_ABSENT"
# -i: a login-like environment for the deployer; stdin is the pinned script (as the workflow's `bash -s`).
sudo -n -i -u "${DEPLOYER}" bash -s < "${SCRIPT}" > "${OUT}" 2>&1
rc=$?
lines=$(wc -l < "${OUT}"); denied=$(grep -c '^DENIED' "${OUT}"); allowed=$(grep -c 'ALLOWED' "${OUT}"); failc=$(grep -c '^FAIL' "${OUT}")
echo "DR5 rc=${rc} lines=${lines} DENIED=${denied} ALLOWED=${allowed} FAIL=${failc} sha256=$(sha256sum < "${OUT}" | cut -c1-64)"
tail -2 "${OUT}"
[[ ${rc} -eq 0 ]] || fail "EXIT_${rc}"
[[ $(tail -2 "${OUT}" | head -1) == "PR1_AUTHORITY_BOUNDARY maturity=P1A-9" ]] || fail "PR1_MATURITY"
[[ $(tail -1 "${OUT}") == "AUTHORITY_BOUNDARY_PROOF=PASS maturity=L1c.3" ]] || fail "MATURITY"
[[ ${allowed} -eq 0 && ${failc} -eq 0 ]] || fail "ALLOWED_OR_FAIL_LINES"
cmp -s "${OUT}" "${EXPECTED}" || { diff -u "${EXPECTED}" "${OUT}" | head -30; fail "NOT_IDENTICAL_TO_EXPECTED_BLOCK"; }
echo "F8_DR5_EQUAL ${EXPECTED_PIN}"
