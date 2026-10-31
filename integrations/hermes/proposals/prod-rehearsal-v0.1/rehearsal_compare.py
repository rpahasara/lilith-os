"""Baseline and comparison for the isolated PROD rehearsal. Reads a copied tree; prints names, counts and digests, never content. Stdlib only.

    python -I -B rehearsal_compare.py baseline <tree> <out.json>
    python -I -B rehearsal_compare.py compare <before.json> <after.json>
    python -I -B rehearsal_compare.py credentials <tree>

Exit 0 means equal, or no credential found. Anything else stops the rehearsal.
"""
import fnmatch
import hashlib
import json
import sqlite3
import sys
from pathlib import Path

CREDENTIALS = (".env", "*.env", "auth.json", "*.key", "*token*.json", "*credentials*", "*.enc", "creds.json")
SKIP_DIRS = {"hermes-agent", "api-venv", "google-venv", "venv", "node_modules", "__pycache__", "cache"}
IDENTITY = ("SOUL.md", "memories/USER.md")
DATABASES = ("lilith-os/data/lilith.db", "lilith-os/data/cognitive_memory.db", "lilith-os/data/privacy_governance.db", "state.db")


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def database(path):
    """One logical digest per table, order-independent. Opened immutable, so a read can't write to the copy."""
    c = sqlite3.connect(f"file:{Path(path).as_posix()}?immutable=1", uri=True)
    try:
        result = {"integrity": c.execute("PRAGMA integrity_check").fetchone()[0], "tables": {}}
        result["schema"] = hashlib.sha256(repr(c.execute("SELECT type, name, tbl_name, COALESCE(sql, '') FROM sqlite_master ORDER BY type, name").fetchall()).encode()).hexdigest()
        for (name,) in c.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name").fetchall():
            rows = sorted(repr(tuple(r)) for r in c.execute(f'SELECT * FROM "{name}"').fetchall())
            result["tables"][name] = {"rows": len(rows), "digest": hashlib.sha256("\n".join(rows).encode()).hexdigest()}
        return result
    finally:
        c.close()


def baseline(tree):
    tree = Path(tree)
    found = {"identity": {}, "databases": {}, "missing": []}
    for name in IDENTITY:
        if (tree / name).is_file():
            found["identity"][name] = sha(tree / name)
        else:
            found["missing"].append(name)
    for name in DATABASES:
        if (tree / name).is_file():
            found["databases"][name] = database(tree / name)
        else:
            found["missing"].append(name)
    return found


def compare(before, after):
    """Every difference, by name. An empty list is the only pass."""
    problems = [f"missing:{n}" for n in after["missing"] if n not in before["missing"]]
    problems += [f"missing_at_baseline:{n}" for n in before["missing"]]
    for name, digest in before["identity"].items():
        if after["identity"].get(name) != digest:
            problems.append(f"identity:{name}")
    for name, old in before["databases"].items():
        new = after["databases"].get(name)
        if new is None:
            problems.append(f"database_gone:{name}")
            continue
        if new["integrity"] != "ok":
            problems.append(f"integrity:{name}")
        if new["schema"] != old["schema"]:
            problems.append(f"schema:{name}")
        for table, value in old["tables"].items():
            if new["tables"].get(table) != value:
                problems.append(f"table:{name}:{table}")
        for table in set(new["tables"]) - set(old["tables"]):
            problems.append(f"table_added:{name}:{table}")
    return sorted(problems)


def credentials(tree):
    tree = Path(tree)
    hits = []
    for path in tree.rglob("*"):
        rel = path.relative_to(tree)
        if path.is_file() and not set(rel.parts) & SKIP_DIRS and any(fnmatch.fnmatch(path.name.lower(), p) for p in CREDENTIALS):
            hits.append(rel.as_posix())
    return sorted(hits)


def main():
    action = sys.argv[1]
    if action == "baseline":
        Path(sys.argv[3]).write_text(json.dumps(baseline(sys.argv[2]), indent=1, sort_keys=True), encoding="utf-8")
        print("BASELINE_WRITTEN")
        return 0
    if action == "compare":
        before, after = (json.loads(Path(p).read_text(encoding="utf-8")) for p in sys.argv[2:4])
        problems = compare(before, after)
        print("\n".join(problems) or "COMPARE_EQUAL")
        return 1 if problems else 0
    hits = credentials(sys.argv[2])
    print("\n".join(hits) or "NO_CREDENTIAL_NAMES")
    return 1 if hits else 0


if __name__ == "__main__":
    sys.exit(main())
