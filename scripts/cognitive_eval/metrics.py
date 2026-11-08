#!/usr/bin/env python3
"""P-2: automatic per-arm measures for replay.py output (E-2 preference recall / over-generalization, E-6 recurrence).

    python metrics.py raw.json spec.json  -> JSON per scenario and per arm

A scenario may declare synthetic checks (case-insensitive regexes):
    "expect": [...]   should appear when the preference applies (correct application)
    "forbid": [...]   must not appear (a recurring corrected behaviour, or a boundary violated)
    "emoji": "none" | "some"   the preference says no emoji / the owner's playful style should survive
A scenario's "kind" ("applies" | "unrelated") separates correct application from over-generalization: on an
"unrelated" scenario, a changed style vs the baseline arm is unwanted application.

Reports rates with denominators, plus mean tokens and latency per arm. Never prints reply text. Standard library only.
"""
from __future__ import annotations

import json
import re
import sys
from collections import defaultdict
from pathlib import Path

_EMOJI = re.compile("[\U0001F300-\U0001FAFF☀-➿\U0001F1E6-\U0001F1FF]")


def check(text: str, scn: dict) -> dict:
    out = {}
    if scn.get("expect"):
        out["expect_hit"] = all(re.search(p, text, re.I) for p in scn["expect"])
    if scn.get("forbid"):
        out["forbid_hit"] = any(re.search(p, text, re.I) for p in scn["forbid"])
    if scn.get("emoji") in ("none", "some"):
        n = len(_EMOJI.findall(text))
        out["emoji_ok"] = (n == 0) if scn["emoji"] == "none" else (n > 0)
    return out


def measure(raw: list, spec: dict) -> dict:
    scns = {s["id"]: s for s in spec["scenarios"]}
    per_arm = defaultdict(lambda: defaultdict(lambda: [0, 0]))      # arm -> "kind:metric" -> [true, n]
    cost = defaultdict(lambda: {"tokens": [], "latency_ms": []})
    per_scn = {}
    errors = defaultdict(int)
    for rec in raw:
        scn = scns.get(rec["id"], {})
        kind = scn.get("kind", "applies")
        per_scn[rec["id"]] = {}
        for arm, replies in rec["replies"].items():
            agg = defaultdict(lambda: [0, 0])
            for text in replies:
                if not text or text.startswith("<<ERROR"):
                    errors[arm] += 1
                    continue
                for m, v in check(text, scn).items():
                    agg[m][0] += int(v)
                    agg[m][1] += 1
                    per_arm[arm]["%s:%s" % (kind, m)][0] += int(v)
                    per_arm[arm]["%s:%s" % (kind, m)][1] += 1
            per_scn[rec["id"]][arm] = {m: "%d/%d" % tuple(v) for m, v in agg.items()}
            cost[arm]["tokens"] += [t for t in rec.get("tokens", {}).get(arm, []) if t]
            cost[arm]["latency_ms"] += [t for t in rec.get("latency_ms", {}).get(arm, []) if t]

    def mean(xs):
        return round(sum(xs) / len(xs)) if xs else None
    return {"arms": {a: {m: "%d/%d" % tuple(v) for m, v in sorted(ms.items())} for a, ms in sorted(per_arm.items())},
            "cost": {a: {"mean_tokens": mean(c["tokens"]), "mean_latency_ms": mean(c["latency_ms"]),
                         "n": len(c["tokens"])} for a, c in sorted(cost.items())},
            "errors": dict(errors), "scenarios": per_scn}


def main(argv=None) -> int:
    a = argv if argv is not None else sys.argv[1:]
    if len(a) != 2:
        print(__doc__)
        return 2
    raw = json.loads(Path(a[0]).read_text(encoding="utf-8"))
    spec = json.loads(Path(a[1]).read_text(encoding="utf-8"))
    print(json.dumps(measure(raw, spec), indent=1, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
