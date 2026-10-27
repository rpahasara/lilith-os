import shutil, subprocess, sys
from pathlib import Path
root = Path(sys.argv[1]); core = root / "services/core-api"
F = core / "lilith_memory/privacy_freshness.py"; A = core / "lilith_memory/privacy_anchor_contracts.py"
R = core / "lilith_memory/privacy_forget_runner.py"; T = root / "services/owner-memory-control/tools/privacy_checkpoint_tool.py"
M = [
 ("M1 gate serves L older than S", F, "        if count < marker[\"suppressionCount\"]:\n            return FreshnessCheck(OLDER_THAN_ANCHOR, marker, count)", "        if count < marker[\"suppressionCount\"]:\n            return FreshnessCheck(READY, marker, count)"),
 ("M2 gate ignores boot id", F, "        if marker[\"bootId\"] != current:", "        if False:"),
 ("M3 gate ignores pending intent", F, "        if pending:\n            return FreshnessCheck(INTENT_PENDING, marker)", "        if False:\n            return FreshnessCheck(INTENT_PENDING, marker)"),
 ("M4 is_held skips freshness", F, "    def is_held(self, memory_class: str, subject_namespace: str, subject_key: str) -> bool:\n        self._freshness.require_ready()", "    def is_held(self, memory_class: str, subject_namespace: str, subject_key: str) -> bool:\n        pass"),
 ("M5 runner ignores barrier refusal", R, "            if refusal is not None:", "            if False:"),
 ("M6 boot check ignores replay entirely", A, "        return BootFreshnessV1(REPLAYED, \"CHALLENGE_NOT_THIS_BOOT\")", "        pass"),
 ("M7 host older than checkpoint accepted", A, "    if doc[\"anchorVersion\"] > chain.version:\n        return OLDER_THAN_CHECKPOINT", "    if doc[\"anchorVersion\"] > chain.version:\n        return FRESH"),
 ("M8 checkpoint allows same anchor version", A, "    _require(doc[\"anchorVersion\"] > previous[\"anchorVersion\"], \"CHECKPOINT_FORK_ALARM\")", "    _require(doc[\"anchorVersion\"] >= previous[\"anchorVersion\"], \"CHECKPOINT_FORK_ALARM\")"),
 ("M9 owner unlock skips its FRESH check", T, "    if not trial.fresh:", "    if False:"),
 ("M10 anchor chain accepts re-append", A, "        _require(not (added & entries), \"ANCHOR_NOT_AN_EXTENSION\")", "        pass"),
]
def run():
    a = subprocess.run([sys.executable, "-m", "unittest", "discover", "-s", "services/core-api/tests", "-p", "test_privacy_freshness.py"], cwd=root, capture_output=True, text=True)
    b = subprocess.run([sys.executable, "-m", "unittest", "discover", "-s", "tests", "-p", "test_privacy_checkpoint_tool.py"], cwd=root / "services/owner-memory-control", capture_output=True, text=True)
    return a.returncode == 0 and b.returncode == 0
caught = 0
for name, path, old, new in M:
    src = path.read_bytes().decode()
    assert src.count(old) == 1, (name, src.count(old))
    try:
        path.write_bytes(src.replace(old, new).encode())
        ok = run()
    finally:
        path.write_bytes(src.encode())
    caught += not ok
    print(("CAUGHT  " if not ok else "SURVIVED"), name)
print(f"mutations caught {caught}/{len(M)}; clean run ok={run()}")
