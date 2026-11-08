"""P-2: the owner's approved social preferences and boundaries, applied where their scope matches (owner turns only).

There is no new store. A preference is an ordinary owner-approved memory (World Model owner memory, #339; approved
LILITH-OS-first, #340; recorded as L18 events, #341) whose text starts with a type and an optional scope:

    Preference: <text>                          global
    Boundary (casual): <text>                   casual / social conversation
    Preference (technical): <text>              technical or work discussion
    Boundary (topic: interviews): <text>        when the message mentions the topic

Changing one is the existing owner-approved replace; retracting it is the existing owner-approved removal. Provenance
and history stay with the memory record.

Per owner turn: read the current approved memories from LILITH OS (local Core API, short cache, fail-open: no note),
keep the typed ones whose scope matches this turn, at most MAX_SELECTED (boundaries first), and render one short note.
The note joins the existing turn guidance on both reply paths. An explicit request in the message wins, and a boundary
wins over any tone suggestion.

Never on a non-owner turn: the caller only asks on owner channels (console, owner Telegram DM, verified Discord DM).
"""

from __future__ import annotations

import json
import re
import time
import urllib.request
from dataclasses import dataclass
from typing import Callable, Iterable, List, Optional, Tuple

KINDS = ("preference", "boundary")
GLOBAL, CASUAL, TECHNICAL = "global", "casual", "technical"
MAX_SELECTED = 3
CACHE_SECONDS = 60.0
API_TIMEOUT = 1.5

_TAG = re.compile(
    r"\A\s*(?P<kind>preference|boundary)\s*(?:\(\s*(?P<scope>global|casual|technical|topic\s*:\s*[^()]{1,40}?)\s*\))?"
    r"\s*[:\-–—]\s*(?P<text>\S.*)\Z", re.IGNORECASE | re.DOTALL)
_WORD = re.compile(r"[a-z0-9]{3,}")

NOTE_HEADER = ("[The owner's approved preferences for this kind of conversation. Apply them naturally, in your own "
               "voice; an explicit request in this message wins, and a boundary wins over any tone suggestion.]")


@dataclass(frozen=True)
class SocialPreferenceV1:
    kind: str                 # preference | boundary
    scope: str                # global | casual | technical | topic:<words>
    text: str                 # the approved wording after the tag
    entry_id: str


def parse(text: str, entry_id: str = "") -> Optional[SocialPreferenceV1]:
    """A typed preference from approved memory text, or None for any other memory."""
    if not isinstance(text, str):
        return None
    m = _TAG.match(text)
    if not m:
        return None
    scope = (m.group("scope") or GLOBAL).strip().lower()
    if scope.startswith("topic"):
        words = " ".join(_WORD.findall(scope.split(":", 1)[1].lower()))
        if not words:
            return None
        scope = "topic:" + words
    body = " ".join(m.group("text").split())
    return SocialPreferenceV1(m.group("kind").lower(), scope, body, entry_id)


def applies(pref: SocialPreferenceV1, *, focused: bool, message: str) -> bool:
    if pref.scope == GLOBAL:
        return True
    if pref.scope == TECHNICAL:
        return focused
    if pref.scope == CASUAL:
        return not focused
    if pref.scope.startswith("topic:"):
        words = set(_WORD.findall((message or "").lower()))
        return any(w in words or (w.rstrip("s") in words) for w in pref.scope[6:].split())
    return False


def select(prefs: Iterable[SocialPreferenceV1], *, focused: bool, message: str) -> List[SocialPreferenceV1]:
    """At most MAX_SELECTED applicable preferences: boundaries first, then the most specific scope, then stable order."""
    rank = {"topic": 0, TECHNICAL: 1, CASUAL: 1, GLOBAL: 2}
    chosen = [p for p in prefs if applies(p, focused=focused, message=message)]
    chosen.sort(key=lambda p: (p.kind != "boundary", rank.get(p.scope.split(":", 1)[0], 3)))
    return chosen[:MAX_SELECTED]


def render(prefs: List[SocialPreferenceV1]) -> Optional[str]:
    if not prefs:
        return None
    lines = ["- %s: %s" % ("Boundary" if p.kind == "boundary" else "Preference", p.text) for p in prefs]
    return NOTE_HEADER + "\n" + "\n".join(lines)


# --------------------------------------------------------------------------------------------- the source ---

class ApprovedPreferenceSource:
    """The current approved owner memories from LILITH OS, cached briefly. Fail-open: on any error, no preferences."""

    def __init__(self, api: str = "http://127.0.0.1:8765", fetch: Optional[Callable[[], list]] = None,
                 clock: Callable[[], float] = time.monotonic, ttl: float = CACHE_SECONDS):
        self._api, self._fetch, self._clock, self._ttl = api.rstrip("/"), fetch, clock, ttl
        self._at: Optional[float] = None
        self._prefs: Tuple[SocialPreferenceV1, ...] = ()

    def _entries(self) -> list:
        if self._fetch is not None:
            return self._fetch()
        with urllib.request.urlopen(self._api + "/os/owner-memory", timeout=API_TIMEOUT) as resp:
            return json.loads(resp.read().decode("utf-8")).get("entries", [])

    def current(self) -> Tuple[SocialPreferenceV1, ...]:
        now = self._clock()
        if self._at is not None and now - self._at < self._ttl:
            return self._prefs
        try:
            entries = self._entries()
            prefs = []
            for e in entries:
                if not isinstance(e, dict) or e.get("lifecycle_state") == "SUPERSEDED":
                    continue
                p = parse(e.get("text"), str(e.get("entry_id") or ""))
                if p is not None:
                    prefs.append(p)
            self._prefs = tuple(prefs)
        except Exception:
            self._prefs = ()                      # fail-open for the turn; retried after the cache period
        self._at = now
        return self._prefs

    def invalidate(self) -> None:
        self._at = None


# -------------------------------------------------------------------------------- durable-correction cues ---
# Explicit owner corrections that MAY be worth remembering. They route the turn to the tool-capable agent (which can
# propose a memory for approval) and add CORRECTION_HINT; they never write anything themselves.
DURABLE_CORRECTION_RE = re.compile(
    r"\b(?:don'?t|do not|stop|quit|never)\s+(?:ever\s+)?(?:call(?:ing)?\s+me|say(?:ing)?|bring(?:ing)?\s+up|"
    r"mention(?:ing)?|use|using|do(?:ing)?\s+that|doing\s+this)\b|"
    r"\bi(?:'ve| have)?\s+(?:already\s+)?told\s+you\b|"
    r"\bthat'?s\s+not\s+what\s+i\s+meant\b|"
    r"\b(?:it|that|this)\s+was\s+(?:only|just)\s+a\s+test\b|"
    r"\bnot\s+a\s+real\s+(?:event|incident|thing|situation)\b",
    re.IGNORECASE,
)

CORRECTION_HINT = (
    "[The owner is correcting you. Acknowledge it briefly and move on; no grovelling. If it reads like a LASTING "
    "preference about how you talk or behave (not a one-off fix of this answer), you may propose remembering it with "
    "the memory tool, worded as 'Preference (scope): ...' or 'Boundary (scope): ...' with scope global, casual, "
    "technical or 'topic: <word>'. Propose only what the owner clearly meant; the owner approves before anything is "
    "kept, so never say it is already saved.]"
)


def durable_correction(message: str) -> bool:
    return bool(DURABLE_CORRECTION_RE.search(message or ""))
