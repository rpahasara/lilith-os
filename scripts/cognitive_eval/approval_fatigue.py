#!/usr/bin/env python3
"""P-4 P4-2: approval-fatigue metric for owner-memory proposals (read-only; counts only; never prints text).

The C-2 consolidation gate (R&D plan 06 §3): if more than half of LILITH's memory proposals are rejected or ignored,
the proposer is tightened. Sources, both existing:
- L18 learning events (GET /os/learning-events): PROPOSED (snapshot job), APPROVED, REJECTED. One proposal can carry
  several items; events are grouped by proposal_id. A proposal approved within one snapshot interval has no PROPOSED
  event, so the proposal set is the union of all three kinds.
- Hermes' pending proposals (~/.hermes/pending/memory/*.json): still waiting for the owner.

Outcome per proposal: approved | rejected | pending (younger than --ignore-days) | ignored (still pending after
--ignore-days, or proposed and gone without approval or rejection). Reported per ISO week of the first event and per
source label, with the fatigue rate = (rejected + ignored) / (approved + rejected + ignored).

    sudo -u lilith python3 approval_fatigue.py [--home ~/.hermes] [--api http://127.0.0.1:8765] [--weeks 8]
"""
from __future__ import annotations

import argparse
import datetime as dt
import glob
import json
import os
import sys
import time
import urllib.request
from collections import defaultdict
from pathlib import Path

SAFE_LABEL = frozenset({"hermes", "nightly", "chat", "in_chat", "cron", "review", "telegram_owner_dm", "lilith_os",
                        "discord_owner_dm", "unknown"})


def _ts(value):
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        pass
    try:
        d = dt.datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return (d if d.tzinfo else d.replace(tzinfo=dt.timezone.utc)).timestamp()
    except ValueError:
        return None


def _label(value) -> str:
    v = str(value or "unknown").strip().lower()
    return v if v in SAFE_LABEL else "other"


def classify(events: list, pending: list, now: float, ignore_days: float = 7.0) -> dict:
    """proposal_id -> {"first": ts, "source": label, "outcome": ...}. `pending` = [(proposal_id, created_ts)]."""
    props = defaultdict(lambda: {"first": None, "source": "unknown", "kinds": set()})
    for e in events:
        pid, kind = e.get("proposal_id"), e.get("kind")
        if not pid or kind not in ("PROPOSED", "APPROVED", "REJECTED"):
            continue
        p = props[str(pid)]
        p["kinds"].add(kind)
        at = _ts(e.get("at"))
        if at is not None and (p["first"] is None or at < p["first"]):
            p["first"] = at
        if kind == "PROPOSED" and e.get("source"):
            p["source"] = _label(e.get("source"))
    waiting = {}
    for pid, created in pending:
        waiting[str(pid)] = created
        p = props[str(pid)]
        if created is not None and (p["first"] is None or created < p["first"]):
            p["first"] = created
    out = {}
    for pid, p in props.items():
        if "APPROVED" in p["kinds"]:
            outcome = "approved"
        elif "REJECTED" in p["kinds"]:
            outcome = "rejected"
        elif pid in waiting:
            age = now - (p["first"] if p["first"] is not None else now)
            outcome = "ignored" if age >= ignore_days * 86400 else "pending"
        else:
            outcome = "ignored"                       # proposed, then gone without approval or rejection
        out[pid] = {"first": p["first"], "source": p["source"], "outcome": outcome}
    return out


def summarize(props: dict, now: float, weeks: int = 8) -> dict:
    keys = ("approved", "rejected", "ignored", "pending")
    def blank():
        return {k: 0 for k in keys}
    total, by_week, by_source = blank(), defaultdict(blank), defaultdict(blank)
    horizon = now - weeks * 7 * 86400
    undated = 0
    for p in props.values():
        o = p["outcome"]
        total[o] += 1
        by_source[p["source"]][o] += 1
        if p["first"] is None:
            undated += 1
        elif p["first"] >= horizon:
            iso = dt.datetime.fromtimestamp(p["first"], dt.timezone.utc).isocalendar()
            by_week["%d-W%02d" % (iso[0], iso[1])][o] += 1

    def rate(c):
        decided = c["approved"] + c["rejected"] + c["ignored"]
        return round((c["rejected"] + c["ignored"]) / decided, 3) if decided else None
    return {"proposals": sum(total.values()), "total": dict(total, fatigue_rate=rate(total)),
            "by_week": {w: dict(c, fatigue_rate=rate(c)) for w, c in sorted(by_week.items())},
            "by_source": {s: dict(c, fatigue_rate=rate(c)) for s, c in sorted(by_source.items())},
            "undated": undated, "gate": "TIGHTEN" if (rate(total) or 0) > 0.5 else "OK",
            "note": "counts only; fatigue_rate = (rejected + ignored) / decided; gate threshold 0.5 (R&D plan 06 §3 C-2)"}


def load_pending(home: Path) -> list:
    out = []
    for path in sorted(glob.glob(str(home / "pending" / "memory" / "*.json"))):
        try:
            rec = json.loads(Path(path).read_text(encoding="utf-8"))
            created = _ts(rec.get("created_at") or rec.get("createdAt")) or os.path.getmtime(path)
        except (OSError, ValueError):
            continue
        out.append((str(rec.get("id") or Path(path).stem), created))
    return out


def load_events(api: str) -> list:
    with urllib.request.urlopen(api.rstrip("/") + "/os/learning-events?limit=5000", timeout=10) as resp:
        return json.loads(resp.read().decode("utf-8")).get("events", [])


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--home", default=os.environ.get("HERMES_HOME") or str(Path.home() / ".hermes"))
    ap.add_argument("--api", default=os.environ.get("LILITH_OS_API_URL", "http://127.0.0.1:8765"))
    ap.add_argument("--weeks", type=int, default=8)
    ap.add_argument("--ignore-days", type=float, default=7.0)
    a = ap.parse_args(argv)
    now = time.time()
    props = classify(load_events(a.api), load_pending(Path(a.home)), now, a.ignore_days)
    print(json.dumps(summarize(props, now, a.weeks), indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
