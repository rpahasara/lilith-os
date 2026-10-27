"""F9-C Slice 3 mutation check: each mutation must make test_privacy_forget_runner fail; sources are restored."""
import hashlib, subprocess, sys
from pathlib import Path
CORE = Path(r"C:\Users\edufo\Documents\Projects\lilith-os-f9c1\services\core-api")
RUN = CORE / "lilith_memory" / "privacy_forget_runner.py"
PG = CORE / "lilith_memory" / "privacy_governance.py"
NL = "\n"
ONLY = __import__("sys").argv[1:]
M = [
 ("env gate removed", RUN, "if deployment_environment != DEV_SYNTHETIC:", "if False:"),
 ("floor check skipped", RUN, "if frozenset(floor) != REQUIRED_FLOOR:", "if False:"),
 ("policy omits floor owners", RUN, "return FAMILY_OWNERS + tuple(sorted(set(floor) - set(FAMILY_OWNERS)))", "return FAMILY_OWNERS"),
 ("adapter pre-check skipped", RUN, "        if missing:" + NL, "        if False:" + NL),
 ("in-flight pre-check skipped", RUN, "if self.privacy_authority.in_flight_authorization(IDENTITY) is not None:" + NL + "            raise ForgetRunnerError(\"FORGET_IN_FLIGHT\")", "if False:" + NL + "            raise ForgetRunnerError(\"FORGET_IN_FLIGHT\")"),
 ("adapter return trusted", RUN, "status = self.privacy_authority.owner_result(ref, nonce, owner)     # only", "status = COMPLETE     # only"),
 ("owner failure ignored", RUN, "                if code is not None:" + NL, "                if False:" + NL),
 ("terminal treated as complete", RUN, "            if status != COMPLETE:" + NL + "                return ForgetRunResult(INCOMPLETE_HOLD_ACTIVE, ref, tuple(completed), policy[position:]," + NL + "                                       failure_code=\"OWNER_RESULT_TERMINAL\"", "            if False:" + NL + "                return ForgetRunResult(INCOMPLETE_HOLD_ACTIVE, ref, tuple(completed), policy[position:]," + NL + "                                       failure_code=\"OWNER_RESULT_TERMINAL\""),
 ("owner-set check skipped", RUN, "if set(authorization.resource_owners) != set(policy):", "if False:"),
 ("completed owners re-run", RUN, "            if status is None:" + NL, "            if True:" + NL),
 ("tampered authorization trusted", RUN, "if authorization is None or authorization.identity != IDENTITY:", "if False:"),
 ("post-commit failure misreported", RUN, "                return self.resume()" + NL, "                pass" + NL),
 ("required_owners always Hermes", PG, "            return self._owner_floor(conn, memory_class, subject_namespace)[1]", "            return frozenset({HERMES_DEV_CONVERSATION})"),
]
orig = {p: p.read_bytes() for p in {RUN, PG}}
sha = {p: hashlib.sha256(b).hexdigest() for p, b in orig.items()}
detected = 0
try:
    for name, path, old, new in [m for m in M if not ONLY or m[0] in ONLY]:
        text = orig[path].decode("utf-8")
        assert text.count(old) == 1, f"mutation anchor not unique: {name}"
        path.write_bytes(text.replace(old, new).encode("utf-8"))
        r = subprocess.run([sys.executable, "-B", "-m", "unittest", "test_privacy_forget_runner"], cwd=CORE / "tests",
                           capture_output=True, text=True, timeout=900)
        ok = r.returncode != 0
        detected += ok
        tail = [l for l in r.stderr.splitlines() if l.startswith(("FAILED", "OK", "Ran "))]
        print(f"{'DETECTED' if ok else 'SURVIVED'}: {name}: {' | '.join(tail)}", flush=True)
        path.write_bytes(orig[path])
finally:
    for p, b in orig.items():
        p.write_bytes(b)
restored = all(hashlib.sha256(p.read_bytes()).hexdigest() == sha[p] for p in orig)
print(f"mutations detected: {detected}/{len(M)}; sources restored: {restored}")
