"""P-4 E-8 follow-up: an episodic timeline note from the World Model's own approved-memory records (no new store).

The profile projection the reply models see (USER.md) is flat current text: it drops WHEN Lilith learned each fact
and WHAT a superseded entry used to say. The World Model keeps both: each owner-memory entry has its approval time,
and a replaced entry stays as SUPERSEDED with the time it stopped being current. E-8 (2026-11-09) showed the reply
model answers when / order / "what was it before" questions correctly only when that information is in front of it,
and honestly says it does not know otherwise.

On an owner turn that asks about time, order or change, this renders a compact timeline from those records:

    - learned 2026-09-02: <approved text>
    - no longer current since 2026-10-20: <superseded text>

"learned" is when the owner told Lilith (the approval), not necessarily when it happened; an event date is used only
when the approved text itself states one. Nothing is inferred, re-dated or changed; the records stay authoritative.
Read-only; owner turns only; deterministic; no model call.
"""

from __future__ import annotations

import datetime as dt
import json
import re
import time
import urllib.request
from typing import Callable, List, Optional, Tuple

TEMPORAL_RE = re.compile(
    r"\bwhen\b|\bwhat\s+(?:came|happened)\s+first\b|\bwhich\s+(?:came|happened)\s+first\b|\bbefore\b|\bafter\b|"
    r"\bago\b|\bhow\s+long\b|\bused\s+to\b|\bpreviously\b|\bever\b|\bback\s+then\b|\bat\s+the\s+time\b|\bsince\b|"
    r"\bfirst\s+time\b|\blast\s+time\b|\bstill\b|\banymore\b|\bchanged?\b|\bmoved\b|\bearlier\b|\bthat\s+time\b",
    re.IGNORECASE)
MAX_ENTRIES = 14
MAX_CHARS = 1600
HEADER = ("[What you know about them, with when you learned it. \"learned\" is when they told you, not necessarily "
          "when it happened; use an event date only if the entry itself states one. An entry marked \"no longer "
          "current\" was true before and has been replaced. Never invent a date or an order you can't see here.]")


def temporal(message: str) -> bool:
    return bool(TEMPORAL_RE.search(message or ""))


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


def render(entries, now: Optional[float] = None) -> Optional[str]:
    """The timeline note from owner-memory records (GET /os/owner-memory?include_superseded=1), or None."""
    rows: List[Tuple[str, str]] = []
    for e in entries or ():
        if not isinstance(e, dict) or not str(e.get("text") or "").strip():
            continue
        text = " ".join(str(e["text"]).split())[:240]
        if e.get("lifecycle_state") == "SUPERSEDED":
            since = _day(e.get("updated_at"))
            rows.append((since or "", "- no longer current%s: %s" % (" since " + since if since else "", text)))
        else:
            learned = _learned(e)
            rows.append((learned or "", "- %s%s" % ("learned %s: " % learned if learned else "undated: ", text)))
    if not rows:
        return None
    rows.sort(key=lambda r: (r[0] == "", r[0]))         # dated first, oldest first; undated last
    lines, size = [], len(HEADER)
    for _, line in rows[-MAX_ENTRIES:]:
        if size + len(line) + 1 > MAX_CHARS:
            break
        lines.append(line)
        size += len(line) + 1
    return HEADER + "\n" + "\n".join(lines)


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
