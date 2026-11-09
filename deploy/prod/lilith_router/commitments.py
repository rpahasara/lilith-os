"""P-4 P4-5c: attention from missed commitments (owner turns only; no model call).

A commitment Lilith made (a reminder or follow-up the scheduler accepted, mirrored into the Goals store by the
commitment sync, P4-4) that did not go out as planned is HER unresolved responsibility:

    BLOCKED                   due, and the scheduler has not run it (missed)
    FAILED within 7 days      the scheduled run failed, or its delivery failed

On the next owner turn the reply may carry one short note so she can own it briefly and offer to reschedule. Rules:
- evidence only: the note states what the scheduler recorded; it never says a message was sent;
- at most once per commitment per gateway process (no nagging); a persistent acknowledgement record is a separate,
  DEV-first step (P4-5c-2);
- the full agent only: a turn that carries the note leaves the fast path (N-48: the small model can echo note text
  verbatim), and the agent can reschedule with its own scheduler tool if the owner wants;
- owner turns only; the read is the local Goals API (read-only GET, 60 s cache, fail-open: no note).
"""

from __future__ import annotations

import datetime as dt
import json
import time
import urllib.request
from typing import Callable, List, Optional, Tuple

FAILED_WINDOW_S = 7 * 86400
CACHE_SECONDS = 60.0
NOTE = ("[Something you owe them: {items}. If it fits this moment, own it briefly in your own words: no excuses, "
        "never say it was sent, and offer to set it up again.]")


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


def unresolved(goals, now: float) -> List[dict]:
    out = []
    for g in goals or ():
        if not isinstance(g, dict) or g.get("type") != "commitment.once":
            continue
        state = g.get("lifecycleState")
        if state == "BLOCKED" or (state == "FAILED" and (_ts(g.get("failedAt")) or 0) >= now - FAILED_WINDOW_S):
            out.append(g)
    return out


def _item(g: dict) -> str:
    title = " ".join(str(g.get("title") or "a reminder").split())[:80]
    how = "the scheduler has not run it" if g.get("lifecycleState") == "BLOCKED" else "its scheduled run failed"
    return "the reminder \"%s\" (due %s): %s" % (title, g.get("deadline") or "earlier", how)


def note(items: List[dict]) -> Optional[str]:
    if not items:
        return None
    return NOTE.format(items="; ".join(_item(g) for g in items[:2]))


class UnresolvedSource:
    """Unresolved commitments from the Goals store, cached briefly; remembers which were already surfaced in this
    process. Fail-open: on any error, nothing."""

    def __init__(self, api: str = "http://127.0.0.1:8765", fetch: Optional[Callable[[], list]] = None,
                 clock: Callable[[], float] = time.time, ttl: float = CACHE_SECONDS):
        self._api, self._fetch, self._clock, self._ttl = api.rstrip("/"), fetch, clock, ttl
        self._at: Optional[float] = None
        self._goals: Tuple[dict, ...] = ()
        self.surfaced: set = set()

    def _load(self) -> list:
        if self._fetch is not None:
            return self._fetch()
        with urllib.request.urlopen(self._api + "/os/goals?limit=200&type=commitment.once", timeout=1.5) as resp:
            return json.loads(resp.read().decode("utf-8")).get("goals", [])

    def pending(self) -> List[dict]:
        """Unresolved commitments not yet surfaced in this process."""
        now = self._clock()
        if self._at is None or now - self._at >= self._ttl:
            try:
                self._goals = tuple(g for g in self._load() if isinstance(g, dict))
            except Exception:
                self._goals = ()
            self._at = now
        return [g for g in unresolved(self._goals, now) if g.get("goalId") not in self.surfaced]

    def mark_surfaced(self, goals) -> None:
        self.surfaced.update(g.get("goalId") for g in goals)
