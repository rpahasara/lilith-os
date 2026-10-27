"""F9-C executor mutation check (WSL, root). Mutates a COPY of the executor (/root/f9c4mut/executor) and requires the
offline matrix to fail for each mutation; the copy is restored after each run and verified at the end."""
import hashlib
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path("/root/f9c4mut/executor")
EX = ROOT / "pkgfiles" / "bin" / "hermes_forget_executor.py"
NL = "\n"
M = [
 ("request field set unchecked", "_require(isinstance(request, dict) and set(request) == REQUEST_FIELDS and request[\"v\"] == 1",
  "_require(isinstance(request, dict) and request[\"v\"] == 1"),
 ("requester uid unchecked", "st.st_uid == cfg.requester_uid and st.st_size", "st.st_size"),
 ("hard links accepted", "and not st.st_mode & 0o002 and st.st_nlink == 1, \"REQUEST_REJECTED\"",
  "and not st.st_mode & 0o002, \"REQUEST_REJECTED\""),
 ("symlinked request followed", "    st = os.lstat(path)" + NL + "    _require(stat.S_ISREG(st.st_mode) and st.st_uid == cfg.requester_uid",
  "    st = os.stat(path)" + NL + "    _require(stat.S_ISREG(st.st_mode) and st.st_uid == cfg.requester_uid"),
 ("authorization result ignored", "    _require(authorization is not None, \"AUTHORIZATION_NOT_VERIFIED\", precondition=True)" + NL,
  "    _require(True, \"AUTHORIZATION_NOT_VERIFIED\", precondition=True)" + NL),
 ("core API pins unchecked", "        _require(path.is_file() and not path.is_symlink() and _sha256_file(path) == cfg.core_api_sha256[name],",
  "        _require(path.is_file() and not path.is_symlink(),"),
 ("other platform tokens allowed", "_require(_env_keys(home / \".env\") <= ALLOWED_ENV_KEYS, \"MULTI_PRINCIPAL_STORE\"",
  "_require(True, \"MULTI_PRINCIPAL_STORE\""),
 ("foreign session sources allowed", "_require(sources <= {\"lilith_os\"}, \"UNRECOGNIZED_SESSION\"", "_require(True, \"UNRECOGNIZED_SESSION\""),
 ("several users allowed", "_require(len(users) <= 1, \"AMBIGUOUS_OWNERSHIP\"", "_require(True, \"AMBIGUOUS_OWNERSHIP\""),
 ("unknown tables ignored", "_require(not unknown, \"UNKNOWN_HERMES_SCHEMA\"", "_require(True, \"UNKNOWN_HERMES_SCHEMA\""),
 ("protected files unchecked", "        _require(unchanged, \"PROTECTED_FILES_CHANGED\")", "        pass"),
 ("tombstone written after deletion",
  "            self.fault(\"backups:before-tombstone\")" + NL + "            _atomic_write(tomb_dir",
  "            for f in found:" + NL + "                remove_backup_item(f)" + NL + "            self.fault(\"backups:before-tombstone\")" + NL + "            _atomic_write(tomb_dir"),
 ("no in-progress marker", "        _atomic_write(self.cfg.marker, json.dumps({\"authDigest\": _digest(ref), \"at\": _utc()}).encode(\"ascii\"))",
  "        pass"),
 ("release without proven Privacy completion",
  "            return bool(store.owner_completion_recorded(ref, OWNER))",
  "            return True"),
 ("reconcile releases unconditionally",
  "        if self.cfg.marker.exists() and not _journals_in_progress(self.cfg.state_dir):",
  "        if self.cfg.marker.exists():"),
 ("journal entries unverified", "        _require(self.host.journal_entries_until(self.cfg.journal_namespace, cutoff) == 0, \"JOURNAL_VERIFY_FAILED\")", "        pass"),
 ("purge follows symlinks", "        if directory.is_symlink():" + NL + "            directory.unlink()",
  "        if False:" + NL + "            directory.unlink()"),
 ("WAL not checkpointed", "            busy = conn.execute(\"PRAGMA wal_checkpoint(TRUNCATE)\").fetchone()" + NL + "            _require(busy is None or busy[0] == 0, \"STATE_DB_CHECKPOINT_BUSY\")" + NL + "            try:",
  "            busy = None" + NL + "            try:"),
 ("final WAL checkpoint removed", "                raise ExecutorError(\"STATE_DB_VACUUM_FAILED\") from exc" + NL + "            busy = conn.execute(\"PRAGMA wal_checkpoint(TRUNCATE)\").fetchone()" + NL + "            _require(busy is None or busy[0] == 0, \"STATE_DB_CHECKPOINT_BUSY\")",
  "                raise ExecutorError(\"STATE_DB_VACUUM_FAILED\") from exc"),
 ("backup scope not limited to HERMES_HOME copies", "        if part in HOME_ROOT_NAMES and i + 1 < len(parts):",
  "        if i + 1 < len(parts):"),
 ("epoch appended twice", "            if entry[\"authDigest\"] == auth:" + NL + "                return int(entry[\"epoch\"])",
  "            if False:" + NL + "                return int(entry[\"epoch\"])"),
 ("FTS left stale", "                    conn.execute(f'INSERT INTO \"{table}\"(\"{table}\") VALUES(\\'rebuild\\')')",
  "                    pass"),
]
orig = EX.read_bytes()
sha = hashlib.sha256(orig).hexdigest()
env = {**os.environ, "F9C_CORE_API": "/root/omc-f9c4/services/core-api", "F9C_EXECUTOR_PKG": str(ROOT / "pkgfiles"),
       "F9C_HERMES_SRC": "/root/f9b/build/pkg/src", "PYTHONPATH": "/root/l1deps:/root/omc-f9c4/services/core-api",
       "PYTHONDONTWRITEBYTECODE": "1"}
only = sys.argv[1:]
detected = total = 0
try:
    for name, old, new in [m for m in M if not only or m[0] in only]:
        total += 1
        text = orig.decode()
        assert text.count(old) == 1, f"anchor not unique ({text.count(old)}): {name}"
        EX.write_bytes(text.replace(old, new).encode())
        r = subprocess.run(["python3", "-B", "-m", "unittest", "test_f9c_executor_matrix"], cwd=ROOT / "tests",
                           env=env, capture_output=True, text=True, timeout=3000)
        ok = r.returncode != 0
        detected += ok
        tail = [l for l in r.stderr.splitlines() if l.startswith(("FAILED", "OK", "Ran "))]
        print(f"{'DETECTED' if ok else 'SURVIVED'}: {name}: {' | '.join(tail)}", flush=True)
        EX.write_bytes(orig)
finally:
    EX.write_bytes(orig)
print(f"mutations detected: {detected}/{total}; source restored: {hashlib.sha256(EX.read_bytes()).hexdigest() == sha}")
