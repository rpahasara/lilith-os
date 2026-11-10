"""P4-1 event-date coverage of real memory proposals: counts only (read-only; never prints, stores or sends text).

Measures whether the nightly review's proposals (after #412 is deployed) carry dates the way its guidance asks:
- event_dated:       an explicit date the owner gave for when it happened ("On 2026-11-09, ...", "on 9 November 2026")
- told_on:           "Told LILITH on <date>: ..." (when they said it; not when it happened)
- relative:          a relative word ("yesterday", "last week", "recently", ...) left without any explicit date
- undated:           a fact with no date and no relative word
- preference:        "Preference (...)" / "Boundary (...)" lines (dates do not apply)
Flags: event_date_equals_review_day (an event date equal to the Colombo day the proposal was made: legitimate when the
owner said "today", but also what a run-date leak looks like; reported for review, never judged here).

Source: GET /os/learning-events?kind=PROPOSED (one row per proposed item: proposal_id, text, at), since a cutoff.
Run ONLY with the owner's explicit OK, on lilith-01, as lilith:
    python3 -I coverage.py --since 2026-11-12T00:00:00+00:00
Output: one JSON object of counts. TEXT_PRINTED is always 0.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import sys
import urllib.request
from collections import Counter

MONTHS = "January|February|March|April|May|June|July|August|September|October|November|December"
ISO = r"\d{4}-\d{2}-\d{2}"
DATE = rf"(?:{ISO}|\d{{1,2}}\s+(?:{MONTHS})\s+\d{{4}}|(?:{MONTHS})\s+\d{{1,2}},?\s+\d{{4}})"
TOLD_RE = re.compile(rf"\btold\s+lilith\s+on\s+({DATE})", re.I)
EVENT_RE = re.compile(rf"(?:^|[.;:]\s*|\b(?:on|since|from|in)\s+)({DATE})\b", re.I)
RELATIVE_RE = re.compile(r"\b(?:today|tonight|yesterday|tomorrow|last\s+(?:week|month|year|night|weekend|"
                         r"monday|tuesday|wednesday|thursday|friday|saturday|sunday)|this\s+(?:week|morning|evening|"
                         r"month)|recently|the\s+other\s+day|a\s+while\s+ago|earlier\s+today|just\s+now)\b", re.I)
PREF_RE = re.compile(r"^\s*(?:Preference|Boundary)\s*\(", re.I)


def _iso(day: str):
    for fmt in ("%Y-%m-%d", "%d %B %Y", "%B %d %Y", "%B %d, %Y"):
        try:
            return dt.datetime.strptime(" ".join(day.replace(",", ", ").split()).replace(" ,", ","), fmt).date()
        except ValueError:
            continue
    return None


def classify(text: str, review_day: dt.date | None = None) -> tuple[str, set]:
    """(class, flags) for one proposed memory text. Pure; the text is only matched, never returned."""
    t = " ".join(str(text or "").split())
    flags: set = set()
    if PREF_RE.search(t):
        return "preference", flags
    told = TOLD_RE.search(t)
    rest = TOLD_RE.sub(" ", t)                         # the told-on date is not an event date
    event = EVENT_RE.search(rest)
    if event:
        d = _iso(event.group(1))
        if review_day and d == review_day:
            flags.add("event_date_equals_review_day")
        if told:
            flags.add("also_told_on")
        return "event_dated", flags
    if told:
        if RELATIVE_RE.search(rest):
            flags.add("relative_kept_with_told_on")
        return "told_on", flags
    if RELATIVE_RE.search(t):
        return "relative", flags
    return "undated", flags


def measure(events: list, since: dt.datetime, zone) -> dict:
    counts, flags, proposals = Counter(), Counter(), set()
    for e in events:
        if e.get("kind") != "PROPOSED" or not e.get("text"):
            continue
        try:
            at = dt.datetime.fromisoformat(str(e.get("at")).replace("Z", "+00:00"))
        except ValueError:
            counts["unparseable_time"] += 1
            continue
        if at.tzinfo is None:
            at = at.replace(tzinfo=dt.timezone.utc)
        if at < since:
            continue
        proposals.add(e.get("proposal_id"))
        cls, fl = classify(e["text"], at.astimezone(zone).date())
        counts[cls] += 1
        flags.update(fl)
    items = sum(v for k, v in counts.items() if k != "unparseable_time")
    dated_facts = counts["event_dated"] + counts["told_on"]
    facts = items - counts["preference"]
    return {"since": since.isoformat(), "proposals": len(proposals), "items": items, "counts": dict(sorted(counts.items())),
            "flags": dict(sorted(flags.items())),
            "fact_items_with_any_date": f"{dated_facts}/{facts}" if facts else "0/0",
            "TEXT_PRINTED": 0}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--since", required=True, help="ISO time; only proposals at or after it (e.g. the #412 deploy)")
    ap.add_argument("--api", default="http://127.0.0.1:8765")
    ap.add_argument("--zone", default="Asia/Colombo")
    a = ap.parse_args(argv)
    from zoneinfo import ZoneInfo
    since = dt.datetime.fromisoformat(a.since)
    if since.tzinfo is None:
        sys.exit("--since needs an offset")
    with urllib.request.urlopen(a.api.rstrip("/") + "/os/learning-events?kind=PROPOSED&limit=5000", timeout=10) as r:
        events = json.loads(r.read().decode("utf-8")).get("events", [])
    print(json.dumps(measure(events, since, ZoneInfo(a.zone))))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
