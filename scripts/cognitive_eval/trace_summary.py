#!/usr/bin/env python3
"""P-1 T-3: read-only summary of LILITH's router decision log (decisions.log).

Prints aggregates only: counts, rates, token sums and latency percentiles, keyed by allow-listed labels (lane, route,
mode, answered_by, provider, model, tone keys). It never prints a free-text field. Any string value that is not a
short label (`[a-z0-9_.:/-]`, ≤64 chars) is counted as "<other>", so no message text, preview or reasoning can leak
even from legacy records. Standard library only; runs on the host as the log owner.

    python3 trace_summary.py --log ~/.hermes/lilith_router/decisions.log --days 7 [--json]
"""
from __future__ import annotations

import argparse
import datetime as _dt
import json
import re
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Iterable, Optional

LABEL = re.compile(r"[a-z0-9_.:/-]{1,64}\Z")


def label(value) -> str:
    if value is None:
        return "<none>"
    if isinstance(value, bool):
        return "true" if value else "false"
    s = str(value).lower()
    return s if LABEL.match(s) else "<other>"


def record_time(rec: dict) -> Optional[float]:
    for key in ("ts", "timestamp"):
        v = rec.get(key)
        if v is None:
            continue
        try:
            return float(v)
        except (TypeError, ValueError):
            try:
                return _dt.datetime.fromisoformat(str(v).replace("Z", "+00:00")).timestamp()
            except ValueError:
                continue
    return None


def percentile(values: list, q: float) -> Optional[int]:
    if not values:
        return None
    s = sorted(values)
    return int(s[min(len(s) - 1, max(0, int(round(q * (len(s) - 1)))))])


def summarize(lines: Iterable[str], since: Optional[float] = None) -> dict:
    lanes, routes, modes, answered, models = Counter(), Counter(), Counter(), Counter(), Counter()
    tone_keys, legacy_preview = Counter(), 0
    stamped, total = 0, 0
    lanes_per_turn = defaultdict(set)
    tokens = defaultdict(lambda: [0, 0])
    durations = defaultdict(list)
    flags = Counter()
    turns = 0
    for line in lines:
        try:
            rec = json.loads(line)
        except (ValueError, TypeError):
            continue
        if not isinstance(rec, dict):
            continue
        t = record_time(rec)
        if since is not None and (t is None or t < since):
            continue
        total += 1
        lane = label(rec.get("lane") or "decision")
        lanes[lane] += 1
        if "preview" in rec:
            legacy_preview += 1
        tid = rec.get("turn_id")
        if tid:
            stamped += 1
            lanes_per_turn[str(tid)].add(lane)
        if lane == "social_route":
            routes[label(rec.get("route"))] += 1
        if lane == "social_cognition_live":
            for k in rec.get("tone_note_keys") or []:
                tone_keys[label(k)] += 1
            if not rec.get("tone_note_keys"):
                tone_keys["<no-note>"] += 1
        if lane == "turn":
            turns += 1
            by = label(rec.get("answered_by"))
            answered[by] += 1
            modes[label(rec.get("mode"))] += 1
            if rec.get("model"):
                models[f"{label(rec.get('provider'))}/{label(rec.get('model'))}"] += 1
            for f in ("fallback_activated", "guard_changed", "d1_recorded", "owner"):
                if rec.get(f) is True:
                    flags[f] += 1
            tokens[by][0] += int(rec.get("tokens_in") or 0)
            tokens[by][1] += int(rec.get("tokens_out") or 0)
            if isinstance(rec.get("duration_ms"), int):
                durations[by].append(rec["duration_ms"])
    per_turn = Counter(len(v) for v in lanes_per_turn.values())
    return {
        "records": total,
        "turn_records": turns,
        "turn_id_coverage": round(stamped / total, 3) if total else None,
        "legacy_preview_records": legacy_preview,
        "lanes": dict(lanes.most_common()),
        "routes": dict(routes.most_common()),
        "turn_modes": dict(modes.most_common()),
        "answered_by": dict(answered.most_common()),
        "models": dict(models.most_common()),
        "rates": {f: round(flags[f] / turns, 3) for f in ("fallback_activated", "guard_changed", "d1_recorded",
                                                          "owner")} if turns else {},
        "tokens": {k: {"in": v[0], "out": v[1], "per_turn": round((v[0] + v[1]) / answered[k], 1)
                       if answered[k] else None} for k, v in tokens.items()},
        "latency_ms": {k: {"p50": percentile(v, 0.5), "p95": percentile(v, 0.95), "n": len(v)}
                       for k, v in durations.items()},
        "tone_keys": dict(tone_keys.most_common()),
        "lane_records_per_turn": {str(k): v for k, v in sorted(per_turn.items())},
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--log", default=str(Path.home() / ".hermes" / "lilith_router" / "decisions.log"))
    ap.add_argument("--days", type=float, default=7.0)
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    since = time.time() - a.days * 86400 if a.days > 0 else None
    try:
        with open(a.log, encoding="utf-8", errors="replace") as fh:
            out = summarize(fh, since)
    except OSError as exc:
        print("cannot read log: %s" % type(exc).__name__, file=sys.stderr)
        return 2
    print(json.dumps(out, indent=None if a.json else 1, sort_keys=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
