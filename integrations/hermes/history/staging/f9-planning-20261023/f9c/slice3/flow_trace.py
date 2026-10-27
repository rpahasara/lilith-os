"""Authorization-flow evidence for F9-C Slice 3: logs every Privacy call (names and outcomes only; refs redacted)."""
import sys, unittest
sys.path.insert(0, r"C:\Users\edufo\Documents\Projects\lilith-os-f9c1\services\core-api\tests")
from test_privacy_forget_runner import RunnerCase, R, HERMES, CountingOwner

LOG = []
METHODS = ("required_owners", "in_flight_authorization", "begin_forget", "resolve_erasure_authorization",
           "owner_result", "record_owner_result", "complete", "suppression_matches")

def shape(v):
    if v is None or isinstance(v, (bool, str)) and len(str(v)) < 24: return v
    if isinstance(v, frozenset): return sorted(v)
    if isinstance(v, tuple) and len(v) == 2 and all(isinstance(x, str) for x in v): return "(<ref>, <nonce>)"
    return type(v).__name__

class Trace(RunnerCase):
    def wrap(self):
        for m in METHODS:
            real = getattr(self.privacy, m)
            def logged(*a, _m=m, _real=real, **k):
                who = k.get("owner") or (a[2] if _m == "owner_result" else (a[2].get("owner") if _m == "record_owner_result" else ""))
                try:
                    out = _real(*a, **k)
                except Exception as e:
                    LOG.append(f"  privacy.{_m}({who}) -> RAISES {type(e).__name__}: {e}"); raise
                LOG.append(f"  privacy.{_m}({who}) -> {shape(out)}"); return out
            setattr(self.privacy, m, logged)

    def test_flow(self):
        self.wrap()
        LOG.append("RUN 1: forget(); Hermes executor queues but never executes (mock crash mode)")
        r1 = self.forget(self.runner(self.owners(**{HERMES: self.hermes(self.mock_executor(mode="crash"))})))
        LOG.append(f"=> {r1.status} failure={r1.failure_code} completed={r1.completed_owners} pending={r1.pending_owners}")
        LOG.append("RUN 2: resume() with a working mock executor")
        r2 = self.runner().resume()
        LOG.append(f"=> {r2.status} completed={r2.completed_owners} receipt={'present' if r2.receipt_id else None}")
        LOG.append("RUN 3: resume() replay after completion")
        r3 = self.runner().resume()
        LOG.append(f"=> {r3.status}")

unittest.main(argv=["x"], exit=False, verbosity=0)
print("\n".join(LOG))
