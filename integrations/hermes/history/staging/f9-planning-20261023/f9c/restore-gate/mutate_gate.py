"""F9-C restore-suppression gate mutation check (Linux copy /root/omc-f9c3g; the Windows worktree is never touched).

Each mutation must make the gate / capture suites (Core API, py3.11 offline FastAPI env) or the owner-memory-control
accepted-read suite (py3.12 + l1deps) fail; sources are restored after each run and verified at the end."""
import hashlib, subprocess, sys
from pathlib import Path

ROOT = Path("/root/omc-f9c3g/services")
CORE = ROOT / "core-api"
PG = CORE / "lilith_memory" / "privacy_governance.py"
MV = CORE / "lilith_memory" / "memory_v2.py"
PY311 = "/root/f9b/build/pkg/python/cpython-3.11.16-linux-x86_64-gnu/bin/python3.11"
NL = "\n"
M = [
 ("gate skips Privacy integrity", PG,
  "        try:" + NL + "            self._privacy.verify_suppression_integrity()" + NL + "        except Exception:" + NL
  + "            return RestoreSuppressionVerification(False, 0, 0, \"PRIVACY_RECORDS_UNVERIFIED\")" + NL + "        try:" + NL
  + "            identities = sorted(",
  "        try:" + NL + "            pass" + NL + "        except Exception:" + NL
  + "            return RestoreSuppressionVerification(False, 0, 0, \"PRIVACY_RECORDS_UNVERIFIED\")" + NL + "        try:" + NL
  + "            identities = sorted("),
 ("gate ignores the L18 probe", PG, "for owner in (l04_owner, l18_owner))", "for owner in (l04_owner,))"),
 ("gate ignores residue", PG, "and any(residue(i) for _, residue in self._probes)", "and False"),
 ("gate drops the in-flight exemption", PG, "if self._privacy.in_flight_authorization(i) is None and any(", "if any("),
 ("gate check error treated as ready", PG,
  "            return RestoreSuppressionVerification(False, 0, 0, \"RESTORE_CHECK_FAILED\")",
  "            return RestoreSuppressionVerification(True, 0, 0, None)"),
 ("require_ready never refuses", PG,
  "        if not verification.ready_to_serve:" + NL + "            raise RestoreSuppressionNotReady",
  "        if False:" + NL + "            raise RestoreSuppressionNotReady"),
 ("resolver is_held skips the gate", PG,
  "        self._gate.require_ready()" + NL + "        return self._privacy.is_held(",
  "        return self._privacy.is_held("),
 ("resolver accepts any gate", PG, "        if not isinstance(gate, RestoreSuppressionGate):", "        if False:"),
 ("facade post-read check removed", MV,
  "        if confirm_ready is not None:" + NL + "            confirm_ready()",
  "        if False:" + NL + "            confirm_ready()"),
 ("helper drops the capture copy", MV,
  "L18V2PrivacyErasureOwner(cognitive_path, privacy_store, capture_evidence_path=capture_evidence_path),",
  "L18V2PrivacyErasureOwner(cognitive_path, privacy_store),"),
]
SUITES = [
    (CORE / "tests", PY311, "/root/coreapi-deps:/root/l1deps",
     ["-m", "unittest", "test_privacy_restore_gate", "test_privacy_restore_capture"]),
    (ROOT / "owner-memory-control", "/usr/bin/python3", "/root/l1deps",
     ["-m", "unittest", "discover", "-s", "tests", "-p", "test_restore_gate_accepted_read.py"]),
]
ENV = {"PATH": "/usr/bin:/bin", "PYTHONDONTWRITEBYTECODE": "1", "HOME": "/root"}


def run_suites():
    tails, failed = [], False
    for cwd, py, pypath, args in SUITES:
        r = subprocess.run([py, "-B", *args], cwd=cwd, capture_output=True, text=True, timeout=1500,
                           env={**ENV, "PYTHONPATH": pypath})
        failed |= r.returncode != 0
        tails += [l for l in r.stderr.splitlines() if l.startswith(("FAILED", "OK", "Ran "))]
    return failed, tails


orig = {p: p.read_bytes() for p in {PG, MV}}
sha = {p: hashlib.sha256(b).hexdigest() for p, b in orig.items()}
baseline_failed, baseline = run_suites()
print(f"baseline (unmutated): {'FAILED' if baseline_failed else 'green'}: {' | '.join(baseline)}", flush=True)
detected = 0
try:
    for name, path, old, new in [m for m in M if len(sys.argv) < 2 or m[0] in sys.argv[1:]]:
        text = orig[path].decode("utf-8")
        assert text.count(old) == 1, f"mutation anchor not unique ({text.count(old)}): {name}"
        path.write_bytes(text.replace(old, new).encode("utf-8"))
        failed, tails = run_suites()
        detected += failed
        print(f"{'DETECTED' if failed else 'SURVIVED'}: {name}: {' | '.join(tails)}", flush=True)
        path.write_bytes(orig[path])
finally:
    for p, b in orig.items():
        p.write_bytes(b)
restored = all(hashlib.sha256(p.read_bytes()).hexdigest() == sha[p] for p in orig)
print(f"mutations detected: {detected}/{len([m for m in M if len(sys.argv) < 2 or m[0] in sys.argv[1:]])}; sources restored: {restored}", flush=True)
