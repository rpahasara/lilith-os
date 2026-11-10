"""P-4 E-8 follow-up: an episodic timeline note from the World Model's own approved-memory records (no new store).

The profile projection the reply models see (USER.md) is flat current text: it drops WHEN Lilith learned each fact
and WHAT a superseded entry used to say. The World Model keeps both: each owner-memory entry has its approval time,
and a replaced entry stays as SUPERSEDED with the time it stopped being current. E-8 (2026-11-09) showed the reply
model answers when / order / "what was it before" questions correctly only when that information is in front of it,
and honestly says it does not know otherwise.

On an owner QUESTION about their own past (when / order / how long ago / before-after / "did I ever" / "do I still"),
this renders a compact list from those records:

    - stored 2026-09-02: <approved text>
    - replaced 2026-10-20 (an earlier stored belief, not necessarily ever true): <superseded text>

Semantics (owner review 2026-11-09):
- a "stored" date is when the memory was recorded, never when an event happened, and never evidence of the order in
  which real-world events occurred; only a date written inside an entry dates an event;
- a replaced entry is what Lilith previously had stored. It may have been true then, mistaken, fictional or corrected;
  it is never presented as a past fact unless a current entry says so.
Entries are listed in their stored order only. Nothing is inferred, re-dated or changed; the records stay
authoritative. Read-only; owner turns only; deterministic; no model call.
"""

from __future__ import annotations

import datetime as dt
import json
import re
import time
import urllib.request
from typing import Callable, List, Optional, Tuple

# A question about the OWNER'S OWN past: time, order, elapsed time, a past state, or whether something still holds.
# Bare words ("when", "before", "after", "ever", "still", "since") in statements, plans, how-to or questions about
# anything else never match (owner review 2026-11-09: a broad cue would route ordinary turns to the full agent).
TEMPORAL_RE = re.compile(
    r"\bwhen\s+(?:did|was|were|have|had)\s+(?:i|we|my)\b|"
    r"\bwhen\s+did\s+you\s+(?:first\s+)?(?:learn|hear|find\s+out)\b|"
    r"\bhow\s+long\s+(?:ago|since|have\s+i|had\s+i|has\s+it\s+been\s+since|did\s+i)\b|"
    r"\bhow\s+many\s+(?:days|weeks|months|years)\s+(?:ago|since)\b|"
    r"\b(?:did|have|had)\s+i\s+ever\b|"
    r"\b(?:where|what|who|how)\s+(?:was|were|did)\s+(?:i|we|my)\b[^?.!]{0,60}?"
    r"\b(?:before|back\s+then|at\s+the\s+time|used\s+to|previously|when\s+i)\b|"
    r"\bwhat\s+did\s+i\s+use\s+to\b|\bdid\s+i\s+use\s+to\b|"
    r"\b(?:do|am|is|are)\s+(?:i|my|we)\b[^?.!]{0,40}?\bstill\b|"
    r"\b(?:before|after)\s+i\s+(?:started|moved|joined|left|passed|failed|quit|got|finished|began)\b",
    re.IGNORECASE)
# "What / which came first" only about the owner's own history: the same question must refer to them (owner review
# of #401: "which came first, the chicken or the egg?", "what happened first in WW2?" must not match).
_FIRST_RE = re.compile(r"\b(?:what|which)\s+(?:came|happened)\s+first\b|\b(?:came|happened)\s+first\s*\?", re.I)
_OWNER_REF_RE = re.compile(r"\b(?:i|i['’](?:d|ve|m)|me|my|mine|we|our|us)\b", re.I)
_QUESTION_RE = re.compile(r"\?|^\s*(?:when|what|which|how|where|who|did|do|have|had|was|were|am|is|are)\b", re.I)
MAX_ENTRIES = 14
MAX_CHARS = 1600
HEADER = ("[Your stored memories about them, in the order they were stored. A \"stored\" date is when the memory "
          "was recorded: never when anything happened, and never a reason to say which real event came first. Only "
          "a date written inside an entry dates an event. A \"replaced\" entry is something you previously had "
          "stored; it may have been mistaken, fictional or corrected, so never present it as what was true unless a "
          "current entry says so. If the dates you need aren't written in an entry, say you don't know.]")


# The full agent can search its past conversations, which hold what the owner said at the time (event-level
# evidence). Offline routing-vs-timeline evaluation 2026-11-09: with HEADER's "say you don't know" the agent stopped
# searching and answered 6/14 temporal questions; with this wording it searched first and answered 14/14 (the agent
# without any note: 12/14). Paths that cannot search keep HEADER.
AGENT_HEADER = HEADER[:-1].rsplit(" If the dates you need", 1)[0] + (
    " For when something happened, what came first or how long ago, check your past conversations with them first, "
    "and prefer what they said at the time over any stored date; only if nothing turns up, say you don't know.]")


# Selective escalation (routing-vs-timeline evaluation, 2026-11-10). A RECORD-level question asks what Lilith has or
# had stored ("how was my name stored before I corrected it?"): the records answer it, so the fast path with the
# timeline suffices (arm D). Every other temporal question is EVENT-level (when it happened, what came first, how long
# ago, where I was then): only conversation evidence answers it, so it escalates to the full agent with search (arm C2
# 12/12; the fast path with or without the timeline stated stale or invented facts there).
_RECORD_LEVEL_RE = re.compile(
    r"\b(?:stored|saved|on\s+file|in\s+your\s+(?:memory|notes))\b|\bbefore\s+i\s+corrected\b|"
    r"\bwhat\s+did\s+you\s+(?:have|keep|write)\s+(?:down\s+)?(?:about|for)\b", re.IGNORECASE)


# Event chronology about the OWNER (owner review of #410): when they did something, what came first, how long ago,
# where/what they were or did then, at the time / back then. Any of these makes a question event-level even when it
# also says "stored", "saved" or "before I corrected" ("what did you have stored, and when did I actually move?").
# "When was my X stored?" is not here: it asks for a storage date, which the record answers.
_EVENT_CUE_RE = re.compile(
    r"\bwhen\s+(?:did|was|were|have|had)\s+(?:i|we)\b|"
    r"\bwhen\s+did\s+you\s+(?:first\s+)?(?:learn|hear|find\s+out)\b|"
    r"\bhow\s+long\s+(?:ago|since|have\s+i|had\s+i|has\s+it\s+been\s+since|did\s+i)\b|"
    r"\bhow\s+many\s+(?:days|weeks|months|years)\s+(?:ago|since)\b|"
    r"\b(?:what|which)\s+(?:came|happened)\s+first\b|\b(?:came|happened)\s+first\b|"
    r"\b(?:what|which)\s+(?:year|month|week|day|date)\b[^?.!]{0,40}?\b(?:did|was|were)\s+(?:i|we)\b|"
    r"\b(?:where|what|who)\s+(?:was|were|did)\s+(?:i|we)\b|"
    r"\b(?:did|have|had)\s+i\s+ever\b|\bused\s+to\b|\bat\s+the\s+time\b|\bback\s+then\b|"
    r"\b(?:before|after)\s+i\s+(?:started|moved|joined|left|passed|failed|quit|got|finished|began)\b",
    re.IGNORECASE)


def needs_conversation(message: str) -> bool:
    """A temporal owner question that only conversation evidence can answer (event-level), as opposed to one only
    about what is stored (record-level). Mixed questions that ask for event chronology are event-level."""
    text = message or ""
    if not temporal(text):
        return False
    return not _RECORD_LEVEL_RE.search(text) or bool(_EVENT_CUE_RE.search(text))


def temporal(message: str) -> bool:
    text = message or ""
    if not _QUESTION_RE.search(text):
        return False
    return bool(TEMPORAL_RE.search(text) or (_FIRST_RE.search(text) and _OWNER_REF_RE.search(text)))


def _day(value) -> Optional[str]:
    if not value:
        return None
    try:
        d = dt.datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    return d.strftime("%Y-%m-%d")


def _learned(entry: dict) -> Optional[str]:
    for p in entry.get("provenance") or ():
        day = _day(p.get("approved_at")) if isinstance(p, dict) else None
        if day:
            return day
    return None                                         # imports and undated records stay undated: never invented


def render(entries, now: Optional[float] = None, can_search: bool = False) -> Optional[str]:
    """The timeline note from owner-memory records (GET /os/owner-memory?include_superseded=1), or None.
    `can_search`: the reader can search past conversations (the full agent), so it is told to look there first."""
    return render_with_ids(entries, can_search=can_search)[0]


def render_with_ids(entries, can_search: bool = False) -> Tuple[Optional[str], List[Optional[str]]]:
    """(note, the entry id of every rendered line, in order; None where a record had no id). The SAME call produces
    the note and its audit ids, so the ids always describe exactly what the reader got (its header and size bounds).
    Ids are opaque record keys; never memory text."""
    header = AGENT_HEADER if can_search else HEADER
    rows: List[Tuple[str, str, Optional[str]]] = []
    for e in entries or ():
        if not isinstance(e, dict) or not str(e.get("text") or "").strip():
            continue
        text = " ".join(str(e["text"]).split())[:240]
        if e.get("lifecycle_state") == "SUPERSEDED":
            since = _day(e.get("updated_at"))
            rows.append((since or "", "- replaced%s (an earlier stored belief, not necessarily ever true): %s"
                         % (" " + since if since else "", text), (str(e["entry_id"]) if e.get("entry_id") else None)))
        else:
            learned = _learned(e)
            rows.append((learned or "", "- %s%s" % ("stored %s: " % learned if learned else "stored (undated): ", text),
                         (str(e["entry_id"]) if e.get("entry_id") else None)))
    if not rows:
        return None, []
    rows.sort(key=lambda r: (r[0] == "", r[0]))         # dated first, oldest first; undated last
    lines, ids, size = [], [], len(header)
    for _, line, eid in rows[-MAX_ENTRIES:]:
        if size + len(line) + 1 > MAX_CHARS:
            break
        lines.append(line)
        ids.append(eid)
        size += len(line) + 1
    return header + "\n" + "\n".join(lines), ids


class OwnerMemorySource:
    """All owner-memory records incl. superseded, from LILITH OS (read-only), cached briefly. Fail-open: none."""

    def __init__(self, api: str = "http://127.0.0.1:8765", fetch: Optional[Callable[[], list]] = None,
                 clock: Callable[[], float] = time.monotonic, ttl: float = 60.0):
        self._api, self._fetch, self._clock, self._ttl = api.rstrip("/"), fetch, clock, ttl
        self._at: Optional[float] = None
        self._entries: Tuple[dict, ...] = ()

    def _load(self) -> list:
        if self._fetch is not None:
            return self._fetch()
        with urllib.request.urlopen(self._api + "/os/owner-memory?include_superseded=1", timeout=1.5) as resp:
            return json.loads(resp.read().decode("utf-8")).get("entries", [])

    def current(self) -> Tuple[dict, ...]:
        now = self._clock()
        if self._at is None or now - self._at >= self._ttl:
            try:
                self._entries = tuple(e for e in self._load() if isinstance(e, dict))
            except Exception:
                self._entries = ()
            self._at = now
        return self._entries
