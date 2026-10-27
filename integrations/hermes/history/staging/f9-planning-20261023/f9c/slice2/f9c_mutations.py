"""Mutation check for F9-C slice 1 (incl. the downgrade-bypass fix): each mutation is applied, the module's suite runs,
and the file is restored byte-for-byte. A mutation must make at least one test fail."""
import subprocess
import sys
from pathlib import Path

ROOT = Path(r"C:\Users\edufo\Documents\Projects\lilith-os-f9c1\services\core-api")
PG = ROOT / "lilith_memory" / "privacy_governance.py"
V2 = ROOT / "lilith_memory" / "privacy_schema_v2.py"
NL = "\n"
MUTATIONS = [
    ("no in-transaction floor re-check", PG,
     '            if self._owner_floor(conn, action.memory_class, action.subject_namespace) != scope:' + NL
     + '                raise PrivacyError("required erasure owner floor changed during FORGET")' + NL, ""),
    ("no pre-consumption scope check", PG, "        self._check_owner_scope(*scope, owners)" + NL, ""),
    ("floor not enforced", PG,
     "        if not floor.issubset(owners):" + NL
     + '            raise PrivacyError("required erasure resource owner is missing")' + NL, ""),
    ("upgrade drops owner rows", V2,
     "        conn.execute(f'INSERT INTO \"{OWNER_TABLE}\" (authorization_ref_id,resource_owner) '" + NL
     + "                     f'SELECT authorization_ref_id,resource_owner FROM \"{OWNER_TABLE_RETIRED}\"')" + NL, ""),
    ("provision without enforcement triggers", V2,
     "        for name in P.FLOOR_ENFORCEMENT_TRIGGERS:" + NL
     + "            conn.execute(FLOOR_ENFORCEMENT_SQL[name])" + NL
     + "        if not _enforcement_exact(conn):" + NL
     + '            raise MigrationError("Hermes owner floor enforcement did not install exactly")' + NL, ""),
    ("authorization trigger neutered", V2,
     "            AND a.{_FI_SCOPE_SQL.format(a='a.')}" + NL, "            AND 0" + NL),
    ("completion trigger neutered", V2,
     "        WHEN OLD.{_FI_SCOPE_SQL.format(a='OLD.')}" + NL, "        WHEN 0" + NL),
    ("runtime tamper check removed", PG,
     "                if int(present) != len(FLOOR_ENFORCEMENT_TRIGGERS):" + NL
     + '                    raise PrivacyError("required erasure owner floor enforcement is missing")' + NL, ""),
    ("in-flight precondition removed", V2,
     "        if int(blocking):" + NL
     + '            raise MigrationError("a First Interaction FORGET without the Hermes owner is in flight; '
       'complete it first")' + NL, ""),
]
failed_to_detect = 0
for name, path, old, new in MUTATIONS:
    original = path.read_bytes()
    text = original.decode("utf-8")
    assert text.count(old) == 1, name
    path.write_text(text.replace(old, new), encoding="utf-8", newline="\n")
    try:
        r = subprocess.run([sys.executable, "-B", "-m", "unittest", "test_privacy_hermes_owner_v2"],
                           cwd=ROOT / "tests", capture_output=True, text=True, timeout=600)
    finally:
        path.write_bytes(original)
    tail = [line for line in r.stderr.splitlines() if line.startswith(("Ran ", "OK", "FAILED"))]
    detected = r.returncode != 0
    failed_to_detect += not detected
    print(f"{'DETECTED' if detected else 'MISSED  '} {name}: {' '.join(tail)}")
print("MUTATIONS", "ALL DETECTED" if not failed_to_detect else f"{failed_to_detect} MISSED")
