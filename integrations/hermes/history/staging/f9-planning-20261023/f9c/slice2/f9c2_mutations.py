"""Mutation check for F9-C slice 2 (adapter + Privacy read helper); files restored byte-for-byte after each."""
import subprocess
import sys
from pathlib import Path

ROOT = Path(r"C:\Users\edufo\Documents\Projects\lilith-os-f9c1\services\core-api")
AD = ROOT / "lilith_memory" / "hermes_erasure_owner.py"
PG = ROOT / "lilith_memory" / "privacy_governance.py"
NL = "\n"
MUTATIONS = [
    ("queued counts as complete", AD,
     "            deadline = self._monotonic() + self.timeout_seconds" + NL,
     "            receipt = {'status': 'COMPLETE'}; return {'owner': self.OWNER, 'status': COMPLETE}" + NL),
    ("receipt not verified", AD, "        bound = verify_receipt(receipt, authorization)" + NL,
     "        bound = {'receiptDigest': 'x', 'erasureEpoch': 1}" + NL),
    ("no re-resolution before record", AD,
     "        self._resolve(authorization_ref_id, execution_nonce)                   # still authorized, hold still ACTIVE" + NL, ""),
    ("no scope check", AD,
     '        _require(authorization.identity == MA.FIRST_INTERACTION_IDENTITY, "AUTHORIZATION_OUT_OF_SCOPE")' + NL, ""),
    ("digest not checked", AD,
     '    _require(isinstance(receipt["receiptDigest"], str) and receipt["receiptDigest"] == receipt_digest(receipt),' + NL
     + '             "RECEIPT_DIGEST_MISMATCH")' + NL, ""),
    ("fingerprint/hold not bound", AD,
     '    _require(receipt["authorizationFingerprint"] == authorization.authorization_fingerprint' + NL
     + '             and receipt["holdId"] == authorization.hold_id, "RECEIPT_AUTHORIZATION_MISMATCH")' + NL, ""),
    ("phases not checked", AD,
     '    _require(isinstance(phases, Mapping) and set(phases) == set(REQUIRED_PHASES)' + NL
     + '             and all(phases[name] == COMPLETE for name in REQUIRED_PHASES), "RECEIPT_INCOMPLETE")' + NL, ""),
    ("overclaim allowed", AD,
     '    _require(receipt["claim"] == CLAIM and receipt["providerErasure"] == PROVIDER_ERASURE, "RECEIPT_OVERCLAIM")' + NL, ""),
    ("environment gate removed", AD,
     '        if deployment_environment != DEV_SYNTHETIC:' + NL
     + '            raise HermesErasureError("INTERIM_V1_PATH_DEV_SYNTHETIC_ONLY")' + NL, ""),
    ("terminal FAILED ignored", AD, '        _require(prior is None, "OWNER_RESULT_TERMINAL")' + NL, ""),
    ("owner_result ignores nonce", PG,
     '                "WHERE e.authorization_ref_id=? AND e.resource_owner=? AND a.execution_nonce=?",' + NL
     + "                (authorization_ref_id, owner, execution_nonce)," + NL,
     '                "WHERE e.authorization_ref_id=? AND e.resource_owner=?",' + NL
     + "                (authorization_ref_id, owner)," + NL),
    ("extra request field (session ids)", AD,
     '            "executionNonce": execution_nonce}' + NL,
     '            "executionNonce": execution_nonce, "sessionIds": ["f8b-s1"]}' + NL),
]
missed = 0
for name, path, old, new in MUTATIONS:
    original = path.read_bytes()
    text = original.decode("utf-8")
    assert text.count(old) == 1, name
    path.write_text(text.replace(old, new), encoding="utf-8", newline="\n")
    try:
        r = subprocess.run([sys.executable, "-B", "-m", "unittest", "test_hermes_erasure_owner"],
                           cwd=ROOT / "tests", capture_output=True, text=True, timeout=600)
    finally:
        path.write_bytes(original)
    tail = [line for line in r.stderr.splitlines() if line.startswith(("Ran ", "OK", "FAILED"))]
    detected = r.returncode != 0
    missed += not detected
    print(f"{'DETECTED' if detected else 'MISSED  '} {name}: {' '.join(tail)}")
print("MUTATIONS", "ALL DETECTED" if not missed else f"{missed} MISSED")
