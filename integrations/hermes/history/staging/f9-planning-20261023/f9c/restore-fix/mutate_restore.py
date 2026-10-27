"""F9-C restore-suppression fix: each mutation must make the restore/capture/runner suites fail; sources restored."""
import hashlib, subprocess, sys
from pathlib import Path
CORE = Path(r"C:\Users\edufo\Documents\Projects\lilith-os-f9c1\services\core-api")
PG = CORE / "lilith_memory" / "privacy_governance.py"
MV = CORE / "lilith_memory" / "memory_v2.py"
NL = "\n"
M = [
 ("verifier ignores L18 identities", PG,
  "{tuple(i) for i in self.l04_owner.list_identities()} | {tuple(i) for i in self.l18_owner.list_identities()}",
  "{tuple(i) for i in self.l04_owner.list_identities()}"),
 ("verifier skips the L18 erase", PG, "                for owner in owners:" + NL + "                    owner.erase_restore_suppressed",
  "                for owner in owners[:1]:" + NL + "                    owner.erase_restore_suppressed"),
 ("verifier residue check removed", PG, "if remaining or any(owner.restore_residue(i) for i in matched for owner in owners):", "if remaining:"),
 ("verifier re-list check removed", PG, "if remaining or any(", "if False or any("),
 ("Privacy integrity check skipped", PG, "            self.privacy_store.verify_suppression_integrity()" + NL, "            pass" + NL),
 ("receipt HMAC not verified", PG, "if not results or not hmac.compare_digest(str(receipt[\"receipt_fingerprint\"]),", "if not results and not hmac.compare_digest(str(receipt[\"receipt_fingerprint\"]),"),
 ("missing selector tolerated", PG, "                    raise PrivacyError(\"privacy restore suppression selector is missing\")", "                    pass"),
 ("in-flight authorization not verified", PG, "                    raise PrivacyError(\"in-flight erasure authorization does not verify\")", "                    pass"),
 ("verifier builds without L18", PG, "        if l04_owner is None or l18_owner is None:", "        if l04_owner is None:"),
 ("verifier erases unsuppressed identities", PG, "matched = [i for i in self._identities() if self.privacy_store.suppression_matches(i)]", "matched = list(self._identities())"),
 ("L18 restore skips suppression proof", MV, "        identity = tuple(identity)" + NL + "        if not privacy_store.suppression_matches(identity):" + NL + "            raise PermissionError(\"RESTORE_SUPPRESSION_NOT_AUTHORIZED\")" + NL + "        self._erase_identity(identity)",
  "        identity = tuple(identity)" + NL + "        self._erase_identity(identity)"),
 ("L18 restore skips the capture copy", MV, "        if self.capture_evidence_path is not None and identity == MA.FIRST_INTERACTION_IDENTITY:" + NL + "            self._erase_capture_evidence(self.capture_evidence_path)" + NL + "        if self.restore_residue(identity):",
  "        if False:" + NL + "            self._erase_capture_evidence(self.capture_evidence_path)" + NL + "        if self.restore_residue(identity):"),
 ("L18 residue omits FI family rows", MV, "            if identity == MA.FIRST_INTERACTION_IDENTITY:" + NL + "                rows += self._first_interaction_rows(conn)", "            if False:" + NL + "                rows += self._first_interaction_rows(conn)"),
 ("L18 listing ignores the capture copy", MV, "        if self._capture_rows():" + NL + "            identities.add(MA.FIRST_INTERACTION_IDENTITY)", "        if False:" + NL + "            identities.add(MA.FIRST_INTERACTION_IDENTITY)"),
 ("L04 restore drops identity admissions", MV, "            identity_refs = self._identity_admission_refs(conn, tuple(identity))" + NL + "            if item is None and not identity_refs:",
  "            identity_refs = ()" + NL + "            if item is None and not identity_refs:"),
 ("L04 residue omits identity admissions", MV, "            return items + len(self._identity_admission_refs(conn, tuple(identity)))", "            return items"),
]
ONLY = sys.argv[1:]
orig = {p: p.read_bytes() for p in {PG, MV}}
sha = {p: hashlib.sha256(b).hexdigest() for p, b in orig.items()}
detected = total = 0
try:
    for name, path, old, new in [m for m in M if not ONLY or m[0] in ONLY]:
        total += 1
        text = orig[path].decode("utf-8")
        assert text.count(old) == 1, f"mutation anchor not unique ({text.count(old)}): {name}"
        path.write_bytes(text.replace(old, new).encode("utf-8"))
        r = subprocess.run([sys.executable, "-B", "-m", "unittest", "test_privacy_restore_suppression",
                            "test_privacy_restore_capture", "test_privacy_forget_runner"], cwd=CORE / "tests",
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
print(f"mutations detected: {detected}/{total}; sources restored: {restored}")
