"""P-4 P4-4b: unbacked-promise check (shadow; metadata only; no model call; never changes a reply).

Rule 1 of the commitments design (work note §3p): Lilith may say a reminder or follow-up is scheduled only when the
scheduler accepted it. This module looks at the finished turn:

    promise          her reply promises a future action of her own ("I'll remind you", "I'll check in tomorrow")
    scheduling_claim her reply says something is scheduled ("I've set a reminder", "your reminder is set")
    scheduled        in this same turn the `cronjob` tool was called with a create action and did not return an error

    unbacked = (promise or scheduling_claim) and not scheduled

Shadow first: the counts decide whether any control is worth building. Only booleans reach the trace.
"""

from __future__ import annotations

import json
import re
from typing import Any, Dict, Iterable, List

_PROMISE_RE = re.compile(
    r"\bI(?:['’]ll| will| am going to|['’]m going to)\s+(?:be\s+)?(?:remind|ping|nudge|check(?:ing)?\s+(?:in|on|back)|"
    r"follow(?:ing)?\s+up|get\s+back\s+to\s+you|message\s+you|text\s+you|circle\s+back|reach\s+out)\b|"
    r"\b(?:will|['’]ll)\s+(?:remind|ping|nudge)\s+you\b",
    re.IGNORECASE,
)
_CLAIM_RE = re.compile(
    r"\bI(?:['’]ve| have)\s+(?:just\s+)?(?:set|scheduled|created|added|booked)\s+(?:up\s+)?(?:a|the|your)\s+"
    r"(?:reminder|follow[- ]?up|check[- ]?in|alarm|nudge)\b|"
    r"\b(?:reminder|follow[- ]?up|check[- ]?in)\s+(?:is|has been)\s+(?:all\s+)?(?:set|scheduled|booked)\b|"
    r"\bscheduled\s+(?:a|the|your)\s+(?:reminder|follow[- ]?up|check[- ]?in)\b",
    re.IGNORECASE,
)
_CREATE_ACTIONS = ("create", "add", "schedule", "new")


def _turn_messages(messages: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """The messages of the last turn: everything after the last user message."""
    msgs = [m for m in messages or [] if isinstance(m, dict)]
    last_user = max((i for i, m in enumerate(msgs) if m.get("role") == "user"), default=-1)
    return msgs[last_user + 1:]


def _args(call: Dict[str, Any]) -> Dict[str, Any]:
    fn = call.get("function") or {}
    raw = fn.get("arguments")
    if isinstance(raw, dict):
        return raw
    try:
        out = json.loads(raw or "{}")
        return out if isinstance(out, dict) else {}
    except (TypeError, ValueError):
        return {}


def _tool_error(content: Any) -> bool:
    text = content if isinstance(content, str) else json.dumps(content, default=str)
    try:
        data = json.loads(text)
        if isinstance(data, dict):
            return bool(data.get("error")) or data.get("success") is False
    except (TypeError, ValueError):
        pass
    return bool(re.search(r"\berror\b|\bfailed\b", text[:300], re.IGNORECASE))


def scheduled_this_turn(messages: Iterable[Dict[str, Any]]) -> bool:
    """True when the turn called the cronjob tool to create a job and that call did not return an error."""
    turn = _turn_messages(messages)
    calls = {}
    for m in turn:
        for c in m.get("tool_calls") or []:
            if isinstance(c, dict) and (c.get("function") or {}).get("name") == "cronjob":
                action = str(_args(c).get("action") or "create").lower()
                if action in _CREATE_ACTIONS:
                    calls[c.get("id")] = True
    if not calls:
        return False
    results = [m for m in turn if m.get("role") == "tool" and m.get("tool_call_id") in calls]
    if not results:
        return False                                   # no tool result: the scheduler's acceptance is not shown
    return any(not _tool_error(m.get("content")) for m in results)


def check(reply: Any, messages: Iterable[Dict[str, Any]]) -> Dict[str, bool]:
    text = reply if isinstance(reply, str) else ""
    promise = bool(_PROMISE_RE.search(text))
    claim = bool(_CLAIM_RE.search(text))
    scheduled = scheduled_this_turn(messages)
    return {"promise": promise, "scheduling_claim": claim, "scheduled": scheduled,
            "unbacked_promise": bool((promise or claim) and not scheduled)}
