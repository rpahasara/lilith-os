"""P-3 batch 3: deterministic, event/goal-based appraisal signals (R&D plan 05 §3). Ephemeral; no model call.

Not an emotion score. An appraisal signal records what happened relative to the owner's own state, from evidence in
this turn and the durable Goals store (L07):

    setback      the owner reports a negative outcome about themselves ("I got rejected", "failed my exam")
    progress     the owner reports a positive outcome ("I passed!", "got the offer")
    goal         the message touches an ACTIVE tracked goal (shared content words with its title)

Effects (only these; mapped to existing approved wording):
    setback  -> the StyleDirective takes Social Cognition's approved `difficulty` line (or `mixed` when they are
                joking about it), never a playful nudge: acknowledge before advising, no forced cheer.
    goal     -> G-WIDEN: one bounded line naming the related goal and its state, so the reply can connect to it.
    progress -> recorded only (there is no approved celebration line; she already celebrates on her own).

Nothing persists (AP-35): "LILITH is sad" is never stored, and history reaches later turns only through approved,
evidenced records. Owner turns only (owner goals are owner data). A technical / help / formal turn keeps its focus.
"""

from __future__ import annotations

import json
import re
import time
import urllib.request
from dataclasses import dataclass
from typing import Callable, Iterable, List, Optional, Sequence, Tuple

from . import metacognition as _mc

# "didn't get the job / make the cut / pass": an outcome, not "didn't get your message" or "didn't get it"
_MISSED = (r"(?:(?:get|land)\s+(?:the|a|an|my|that|this)\s+(?:\w+\s+)?(?:job|role|offer|place|position|spot|grant|"
           r"visa|promotion|interview|contract|internship|scholarship)\b|get\s+(?:in|into|through|hired|picked|selected|"
           r"accepted|shortlisted)\b|make\s+(?:it|the\s+cut|the\s+team|the\s+shortlist)\b|pass\b|finish\b)")
_SETBACK_RE = re.compile(
    r"\b(?:i|we)(?:'ve|\s+have)?\s+(?:just\s+)?(?:got|was|were|been|get|am|'m)\s+(?:\w+\s+)?"
    r"(?:rejected|turned\s+down|laid\s+off|let\s+go|fired|ghosted|dumped)\b|"
    r"\b(?:i|we)\s+(?:just\s+)?(?:didn'?t|did\s+not|couldn'?t|could\s+not)\s+" + _MISSED + r"|"
    r"\b(?:i|we)\s+(?:just\s+)?(?:failed|flunked|bombed|blew|lost)\b(?!\s+to\b)|"
    r"\b(?:got|received|another)\s+(?:a\s+|the\s+|my\s+)?rejection\b|\bno\s+offer\b|\bthey\s+(?:rejected|passed\s+on)\s+me\b|"
    r"\b(?:my|the|our)\s+(?:\w+\s+){1,3}?(?:got\s+|was\s+)?(?:rejected|cancelled|canceled|fell\s+through)\b|"
    r"^\W*(?:just\s+)?(?:(?:failed|flunked|bombed|blew)\b(?!\s+to\b)|didn'?t\s+" + _MISSED + r"|got\s+(?:rejected|"
    r"turned\s+down|laid\s+off|fired|ghosted)\b)",
    re.IGNORECASE,
)
_PROGRESS_RE = re.compile(
    r"\b(?:i|we)(?:'ve|\s+have)?\s+(?:just\s+|finally\s+)?(?:passed|nailed|aced|finished|shipped|landed|cleared)\b|"
    r"\b(?:i|we)\s+(?:just\s+|finally\s+)?got\s+(?:the\s+|an?\s+)?(?:offer|job|role|promotion|interview|place|in|accepted|hired)\b|"
    r"\b(?:i|we)(?:'m|\s+am|\s+was|\s+got)\s+(?:officially\s+)?(?:hired|accepted|promoted|certified)\b|"
    r"^\s*(?:just\s+|finally\s+)?got\s+the\s+(?:offer|job|role|promotion)\b",
    re.IGNORECASE,
)
_NEGATED_PROGRESS_RE = re.compile(r"\b(?:didn'?t|did\s+not|haven'?t|not)\s+(?:\w+\s+)?(?:pass|get|finish|land)", re.I)
ACTIVE_STATES = ("ACTIVE", "PROPOSED", "BLOCKED", "SUSPENDED")
MAX_GOALS = 1
# words every career goal title carries ("Follow up on application 12 - <role> at <company>"): never evidence alone
_TITLE_STOP = frozenset({"follow", "application", "role", "company", "goal", "track", "tracking", "job", "work"})


@dataclass(frozen=True)
class AppraisalSignal:
    kind: str                      # setback | progress | goal
    ref: str = ""                  # goal id for kind=goal
    state: str = ""                # goal lifecycle state for kind=goal


def outcome(message: str) -> Optional[str]:
    text = message or ""
    if _SETBACK_RE.search(text):
        return "setback"
    if _PROGRESS_RE.search(text) and not _NEGATED_PROGRESS_RE.search(text):
        return "progress"
    return None


def related_goals(message: str, goals: Iterable[dict]) -> List[dict]:
    """Active goals whose title shares a content word with the message (at most MAX_GOALS, in store order)."""
    terms = _mc.key_terms(message) - _TITLE_STOP
    if not terms:
        return []
    out = []
    for g in goals or ():
        if not isinstance(g, dict) or str(g.get("lifecycleState") or "").upper() not in ACTIVE_STATES:
            continue
        if _mc.covered(terms, str(g.get("title") or "")):
            out.append(g)
        if len(out) >= MAX_GOALS:
            break
    return out


def appraise(message: str, goals: Iterable[dict] = ()) -> Tuple[AppraisalSignal, ...]:
    sigs: List[AppraisalSignal] = []
    oc = outcome(message)
    if oc:
        sigs.append(AppraisalSignal(oc))
    for g in related_goals(message, goals):
        sigs.append(AppraisalSignal("goal", str(g.get("goalId") or ""), str(g.get("lifecycleState") or "")))
    return tuple(sigs)


def adjust_lines(lines: Sequence[str], signals: Sequence[AppraisalSignal], *, focused: bool) -> Tuple[str, ...]:
    """Map a setback onto the approved Social Cognition lines (same precedence as tone_note_keys)."""
    keys = list(lines or ())
    if focused or "formal" in keys or not any(s.kind == "setback" for s in signals):
        return tuple(keys)
    if "support" in keys or "difficulty" in keys or "mixed" in keys:
        return tuple(keys)
    if "playful" in keys:
        return tuple("mixed" if k == "playful" else k for k in keys)
    pos = len([k for k in keys if k in ("correction", "support")])
    return tuple(keys[:pos] + ["difficulty"] + keys[pos:])


GOAL_NOTE = ("[This touches a goal they're tracking: \"{title}\" (status: {state}). Connect to it only if it fits; "
             "don't recite it.]")


def goal_note(goals: Sequence[dict]) -> Optional[str]:
    if not goals:
        return None
    g = goals[0]
    title = " ".join(str(g.get("title") or "").split())[:120]
    if not title:
        return None
    return GOAL_NOTE.format(title=title, state=str(g.get("lifecycleState") or "unknown").lower())


# ------------------------------------------------------------------------------------------ the goal source ---

class GoalSource:
    """The owner's tracked goals from the durable Goals store (local Core API, read-only GET /os/goals), cached
    briefly. Fail-open: on any error, no goals (and so no goal signal)."""

    def __init__(self, api: str = "http://127.0.0.1:8765", fetch: Optional[Callable[[], list]] = None,
                 clock: Callable[[], float] = time.monotonic, ttl: float = 60.0, timeout: float = 1.5):
        self._api, self._fetch, self._clock, self._ttl, self._timeout = api.rstrip("/"), fetch, clock, ttl, timeout
        self._at: Optional[float] = None
        self._goals: Tuple[dict, ...] = ()

    def _load(self) -> list:
        if self._fetch is not None:
            return self._fetch()
        with urllib.request.urlopen(self._api + "/os/goals?limit=200", timeout=self._timeout) as resp:
            return json.loads(resp.read().decode("utf-8")).get("goals", [])

    def current(self) -> Tuple[dict, ...]:
        now = self._clock()
        if self._at is not None and now - self._at < self._ttl:
            return self._goals
        try:
            self._goals = tuple(g for g in self._load() if isinstance(g, dict))
        except Exception:
            self._goals = ()
        self._at = now
        return self._goals
