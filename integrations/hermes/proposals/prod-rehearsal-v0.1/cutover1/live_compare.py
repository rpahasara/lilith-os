"""rehearsal_compare.py against a live tree. Opens each database read-only and through its WAL, never immutable. Prints names, counts and digests, never content. Stdlib only.

    python -I -B live_compare.py baseline <tree>                 JSON on stdout
    python -I -B live_compare.py judge <pre> <post> [<a> <b>]... a table that moved between an a/b control pair may have grown; anything else that differs is unexpected

Exit 0 means nothing unexpected.
"""
import json
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import rehearsal_compare as R


R.sqlite3 = type("Live", (), {"connect": staticmethod(lambda u, **k: sqlite3.connect(u.replace("immutable=1", "mode=ro"), uri=True, timeout=10.0))})


def load(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def rows(baseline, item):
    _, database, table = item.split(":", 2)
    return baseline["databases"].get(database, {}).get("tables", {}).get(table, {}).get("rows", -1)


def judge(pre, post, pairs):
    moving = set()
    for a, b in pairs:
        moving |= {p for p in R.compare(a, b) if p.startswith(("table:", "table_added:"))}
    unexpected, moved = [], []
    for item in R.compare(pre, post):
        if item not in moving:
            unexpected.append(item)
        elif item.startswith("table:") and rows(post, item) < rows(pre, item):
            unexpected.append("rows_fell:" + item)
        else:
            moved.append(item)
    return unexpected, moved


def main():
    if sys.argv[1] == "baseline":
        print(json.dumps(R.baseline(sys.argv[2]), indent=1, sort_keys=True))
        return 0
    docs = [load(p) for p in sys.argv[2:]]
    pairs = list(zip(docs[2::2], docs[3::2]))
    unexpected, moved = judge(docs[0], docs[1], pairs)
    print("\n".join("UNEXPECTED " + u for u in unexpected + []) or "JUDGE_EQUAL moved %d" % len(moved))
    for m in moved:
        print("MOVED", m)
    return 1 if unexpected else 0


if __name__ == "__main__":
    sys.exit(main())
