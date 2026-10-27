"""Per-conversation router state: previous mode + bounded recent messages.

In-memory only (process-local), thread-safe, and LRU-bounded so it cannot grow
without limit. State resetting on gateway restart is acceptable — continuity of
the actual conversation is preserved by Hermes' session DB; this only carries
lightweight routing hints. No secrets are stored.
"""

from __future__ import annotations

import threading
from collections import OrderedDict, deque
from dataclasses import dataclass, field
from typing import Deque, List, Optional

_MAX_SESSIONS = 2000
_MAX_RECENT = 12


@dataclass
class _Entry:
    previous_mode: Optional[str] = None
    recent: Deque[str] = field(default_factory=lambda: deque(maxlen=_MAX_RECENT))
    # Last social reply actually delivered (post-guard), for pet-name adjacency.
    last_social_reply: Optional[str] = None


class RouterState:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._sessions: "OrderedDict[str, _Entry]" = OrderedDict()

    def _entry(self, key: str) -> _Entry:
        entry = self._sessions.get(key)
        if entry is None:
            entry = _Entry()
            self._sessions[key] = entry
            while len(self._sessions) > _MAX_SESSIONS:
                self._sessions.popitem(last=False)
        else:
            self._sessions.move_to_end(key)
        return entry

    def previous_mode(self, key: str) -> Optional[str]:
        with self._lock:
            entry = self._sessions.get(key)
            return entry.previous_mode if entry else None

    def recent(self, key: str, n: int) -> List[str]:
        with self._lock:
            entry = self._sessions.get(key)
            if not entry:
                return []
            items = list(entry.recent)
            return items[-n:] if n > 0 else items

    def record(self, key: str, message: str, mode: str) -> None:
        with self._lock:
            entry = self._entry(key)
            if message:
                entry.recent.append(message)
            entry.previous_mode = mode

    def last_social_reply(self, key: str) -> Optional[str]:
        with self._lock:
            entry = self._sessions.get(key)
            return entry.last_social_reply if entry else None

    def record_social_reply(self, key: str, reply: str) -> None:
        with self._lock:
            entry = self._entry(key)
            entry.last_social_reply = reply or None


# Process-global singleton.
STATE = RouterState()
