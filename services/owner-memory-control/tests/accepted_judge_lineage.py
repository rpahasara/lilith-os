"""Test helper: the one accepted change a historical bundle closure may show against HEAD.

The M-B1 / M-B3 ceremony closures were pinned while `pr1_acceptance.py` was the aee323e judge (`e0928854`). Since then
it changed only through the two owner-accepted judge corrections, whose exact edits are pinned in their contracts:
E-19 (`e19_p1b10_upgrade.E19_EDITS`, `0d2e6cca`) and E-22 / OD-M12-10 (`e22_judge_upgrade.E22_EDITS`, `d3df4cfc`).

`closure_delta_is_the_accepted_judge` admits a closure diff only if `pr1_acceptance.py` is the sole changed path and
the HEAD bytes, with exactly the E-22 and then the E-19 edits undone, are byte-identical to the bytes at the ceremony's
own source commit. Every other closure path must be unchanged.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
TOOLS = ROOT / "services/owner-memory-control/tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import e19_p1b10_upgrade as E19  # noqa: E402
import e22_judge_upgrade as E22  # noqa: E402

JUDGE = E22.PR1_ACCEPTANCE_SOURCE          # services/owner-memory-control/lilith_owner_memory/pr1_acceptance.py
AEE323E_JUDGE_SHA256 = "e0928854e1fcf4107458939ba9ebf1903cf7a4d0ab6808f7e89108db1444bbff"
HEAD_JUDGE_SHA256 = E22.PR1_ACCEPTANCE_NEW_SHA256  # d3df4cfc (E-22, OD-M12-10)


def closure_delta_is_the_accepted_judge(testcase, source_commit: str, changed_paths: str) -> None:
    import hashlib

    changed = {line.strip() for line in changed_paths.splitlines() if line.strip()}
    testcase.assertEqual(changed - {JUDGE}, set())                     # every other pinned path is unchanged
    testcase.assertEqual(changed, {JUDGE})                             # and the judge did move (E-19, E-22)
    at_source = subprocess.run(["git", "-C", str(ROOT), "show", f"{source_commit}:{JUDGE}"], capture_output=True,
                               check=True).stdout
    head = subprocess.run(["git", "-C", str(ROOT), "show", f"HEAD:{JUDGE}"], capture_output=True, check=True).stdout
    testcase.assertEqual(hashlib.sha256(at_source).hexdigest(), AEE323E_JUDGE_SHA256)
    testcase.assertEqual(hashlib.sha256(head).hexdigest(), HEAD_JUDGE_SHA256)
    testcase.assertEqual(E19.reverse_e19(E22.reverse_e22(head)), at_source)   # exactly the accepted edits, nothing else
