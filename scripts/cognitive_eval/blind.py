#!/usr/bin/env python3
"""P-1 T-5: blind comparison sheets and scoring for replay.py output. Standard library only; runs anywhere.

    python blind.py make  raw.json scenarios.json --seed tag  -> tag_blind.md, tag_key.json, tag_verdicts.json (template)
    python blind.py score tag_key.json tag_verdicts.json      -> per-arm mean rating and per-scenario win rates

The rater (the owner) fills tag_verdicts.json with a rating 1-5 per label, or null to skip, without seeing the key. The
key never enters the blind sheet. Scoring reports denominators, ties and skips (AP-34, SM-43).
"""
from __future__ import annotations

import json
import random
import sys
from collections import defaultdict
from pathlib import Path


def make(raw: list, scenarios: dict, seed: str):
    """Return (markdown, key, verdict template). Deterministic for a given seed."""
    rng = random.Random("blind-" + seed)
    lines, key, template = [], {}, {}
    for rec in raw:
        scn = scenarios.get(rec["id"], {})
        lines.append("## %s" % rec["id"])
        for role, text in scn.get("history", []):
            lines.append("> %s: %s" % (role, text))
        lines.append("> user: %s\n" % scn.get("message", ""))
        items = [(arm, i, t) for arm, ts in rec["replies"].items() for i, t in enumerate(ts) if t]
        rng.shuffle(items)
        for n, (arm, i, text) in enumerate(items, 1):
            lab = "%s#%d" % (rec["id"], n)
            key[lab] = arm
            template[lab] = None
            lines.append("**[%s]** %s\n" % (lab, text))
    md = "\n".join(lines)
    return md, key, template


def score(key: dict, verdicts: dict) -> dict:
    arms = defaultdict(list)
    per_scn = defaultdict(lambda: defaultdict(list))
    skipped = 0
    for lab, arm in key.items():
        v = verdicts.get(lab)
        if not isinstance(v, (int, float)) or not 1 <= v <= 5:
            skipped += 1
            continue
        arms[arm].append(float(v))
        per_scn[lab.rsplit("#", 1)[0]][arm].append(float(v))
    wins, ties, compared = defaultdict(int), 0, 0
    for scn, by_arm in per_scn.items():
        if len(by_arm) < 2:
            continue
        compared += 1
        means = {a: sum(v) / len(v) for a, v in by_arm.items()}
        best = max(means.values())
        top = [a for a, m in means.items() if m == best]
        if len(top) > 1:
            ties += 1
        else:
            wins[top[0]] += 1
    return {"ratings": {a: {"n": len(v), "mean": round(sum(v) / len(v), 2)} for a, v in sorted(arms.items())},
            "scenario_wins": dict(wins), "scenario_ties": ties, "scenarios_compared": compared,
            "skipped": skipped, "labels": len(key)}


def main(argv=None) -> int:
    a = argv if argv is not None else sys.argv[1:]
    if a and a[0] == "make" and len(a) >= 3:
        raw = json.loads(Path(a[1]).read_text(encoding="utf-8"))
        spec = json.loads(Path(a[2]).read_text(encoding="utf-8"))
        seed = a[a.index("--seed") + 1] if "--seed" in a else "run"
        md, key, tpl = make(raw, {s["id"]: s for s in spec["scenarios"]}, seed)
        Path(seed + "_blind.md").write_text(md, encoding="utf-8")
        Path(seed + "_key.json").write_text(json.dumps(key, indent=1), encoding="utf-8")
        Path(seed + "_verdicts.json").write_text(json.dumps(tpl, indent=1), encoding="utf-8")
        print("wrote %s_blind.md, %s_key.json (keep closed), %s_verdicts.json (fill 1-5 or null)" % (seed, seed, seed))
        return 0
    if a and a[0] == "score" and len(a) == 3:
        print(json.dumps(score(json.loads(Path(a[1]).read_text(encoding="utf-8")),
                               json.loads(Path(a[2]).read_text(encoding="utf-8"))), indent=1))
        return 0
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main())
