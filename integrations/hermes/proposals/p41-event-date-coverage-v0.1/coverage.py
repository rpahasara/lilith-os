"""P4-1 event-date coverage of real memory proposals: counts only (read-only; never prints, stores or sends text).

Measures whether the nightly review's proposals (after #412 is deployed) carry dates the way its guidance asks:
- event_dated:       an explicit date the owner gave for when it happened ("On 2026-11-09, ...", "on 9 November 2026")
- told_on:           "Told LILITH on <date>: ..." (when they said it; not when it happened)
- relative:          a relative word ("yesterday", "last week", "recently", ...) left without any explicit date
- undated:           a fact with no date and no relative word
- preference:        "Preference (...)" / "Boundary (...)" lines (dates do not apply)
Known limits (see README): English phrasing only; one class per proposed item (an item stating several facts counts
once); a date anywhere in the item counts, including a future plan's date; year-only and month-only dates count as
event_dated with the flag partial_date; removals are counted apart.
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

MONTHS = (r"jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|june?|july?|aug(?:ust)?|sep(?:t(?:ember)?)?|"
          r"oct(?:ober)?|nov(?:ember)?|dec(?:ember)?")
WEEKDAYS = r"monday|tuesday|wednesday|thursday|friday|saturday|sunday"
ISO = r"\d{4}-\d{2}-\d{2}"
DM = rf"\d{{1,2}}(?:st|nd|rd|th)?\s+(?:of\s+)?(?:{MONTHS})\.?(?:,?\s+\d{{4}})?"           # 3 November [2026], 3rd Nov
MD = rf"(?:{MONTHS})\.?\s+\d{{1,2}}(?:st|nd|rd|th)?(?:,?\s+\d{{4}})?"                       # November 3[, 2026]
DATE = rf"(?:{ISO}|{DM}|{MD})"
PARTIAL = rf"(?:(?:in|since|from)\s+(?:(?:{MONTHS})\s+)?(?:19|20)\d{{2}})"                    # in 2024, since May 2023
TOLD_RE = re.compile(rf"\btold\s+lilith\s+on\s+({DATE})", re.I)
EVENT_RE = re.compile(rf"(?:^|[.;:,]\s*|\b(?:on|since|from|in|by)\s+)(?:(?:{WEEKDAYS}),?\s+)?({DATE})\b", re.I)
PARTIAL_RE = re.compile(rf"\b{PARTIAL}\b", re.I)
RELATIVE_RE = re.compile(r"\b(?:today|tonight|yesterday|tomorrow|last\s+(?:week|month|year|night|weekend|"
                         rf"{WEEKDAYS})|this\s+(?:past\s+)?(?:week|weekend|morning|evening|month|year)|recently|"
                         r"the\s+other\s+day|a\s+while\s+ago|earlier\s+today|just\s+now|"
                         r"(?:\d+|a|an|one|two|three|four|five|six|seven|eight|nine|ten|a\s+few|a\s+couple\s+of|several)\s+"
                         rf"(?:days?|weeks?|months?|years?)\s+ago|on\s+(?:{WEEKDAYS})\b(?!,?\s+\d))", re.I)
PREF_RE = re.compile(r"^\s*(?:Preference|Boundary)\s*\(", re.I)


def _iso(day: str, review_day: dt.date | None = None):
    """A date for the flag check; a year-less date takes the review day's year (the previous year if it would be in
    the future). None when it cannot be read."""
    s = re.sub(r"(\d)(st|nd|rd|th)\b", r"\1", " ".join(day.replace(",", " ").split()), flags=re.I).replace(" of ", " ")
    s = re.sub(r"\.", "", s)
    try:
        return dt.date.fromisoformat(s)
    except ValueError:
        pass
    for fmt in ("%d %B %Y", "%d %b %Y", "%B %d %Y", "%b %d %Y", "%d %B", "%d %b", "%B %d", "%b %d"):
        try:
            d = dt.datetime.strptime(s.title() if not s[0].isdigit() else s[:3] + s[3:].title(), fmt).date()
        except ValueError:
            continue
        if "%Y" not in fmt and review_day:
            d = d.replace(year=review_day.year)
            if d > review_day:
                d = d.replace(year=review_day.year - 1)
        return d
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
        d = _iso(event.group(1), review_day)
        if d is None:
            flags.add("unparsed_date")
        elif review_day and d == review_day:
            flags.add("event_date_equals_review_day")
        if told:
            flags.add("also_told_on")
        return "event_dated", flags
    if PARTIAL_RE.search(rest):
        flags.add("partial_date")                       # a year or month only: dated, but coarsely
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
        if e.get("detail") == "remove":                 # a proposed removal is not a proposed fact
            counts["removals"] += 1
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
    items = sum(v for k, v in counts.items() if k not in ("unparseable_time", "removals"))
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
