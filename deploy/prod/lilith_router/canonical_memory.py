"""LILITH Router V2: canonical memory for a turn (PROD; PREPARED, not deployed).

One call per turn from `gateway_integration.route_turn`, before routing:

    channel = owner_channel(platform, source, owner_telegram_ids)
        "lilith_os"          the authenticated Command Center console
        "telegram_owner_dm"  ONLY a Telegram private chat whose user id is one of the configured owner ids AND equals
                             the chat id (Telegram private chats use the user id as the chat id)
        "public"             everything else: Discord (any channel or DM), Telegram groups, other users, other platforms
    note = turn_note(...)    the root context service's answer for that channel, rendered by the shared renderer

The root service (canonical_context_service.py) gives owner-personal memory only to a channel the owner's grant lists,
and "public" can never be listed. Owner decision 2026-11-06: a "public" turn does not even ask the service, so
Discord, Telegram groups, other users and other platforms get no canonical memory at all.

Then `merge(result, ...)` puts the note into the ephemeral prompt on every route that runs the main agent. The note
is part of the prompt the agent was built with, so when it changes (a new admission, a FORGET, an expired grant) the
cached agent is rebuilt once. The lean social reply gets it through `current_note()`. Ready answers that make no main
model call (Reasoning, Planning, Ethics) are unchanged.

Settings: `HERMES_HOME/lilith_router/canonical_memory.json`, root-owned and read-only to the gateway like the rest of
`lilith_router/`. It is absent or `enabled: false` until the owner's activation step, so installing this module
changes nothing:

    {"schemaVersion": 1, "enabled": true, "ownerTelegramUserIds": ["<the owner's Telegram user id>"]}

Fail-open for the turn, fail-closed for memory: any error means no note, never a guessed one. Nothing is written.
"""

from __future__ import annotations

import contextvars
import hashlib
import json
import os
import re
import stat
from pathlib import Path
from typing import Any, Iterable, Optional

from . import lilith_memory_context as _ctx

OWNER_CONSOLE = "lilith_os"
OWNER_TELEGRAM = "telegram_owner_dm"
PUBLIC = "public"
DEFAULT_TIMEOUT = 10.0
SETTINGS_NAME = "canonical_memory.json"
_SETTINGS_FIELDS = frozenset({"schemaVersion", "enabled", "ownerTelegramUserIds"})
_TELEGRAM_ID = re.compile(r"[0-9]{1,20}\Z")
_SESSION = re.compile(r"[A-Za-z0-9._:-]{1,128}\Z")

_note: contextvars.ContextVar = contextvars.ContextVar("lilith_canonical_note", default=None)
_built_with: dict = {}            # session key -> digest of the note the cached agent was built with


def owner_channel(platform: str, source: Any, owner_telegram_ids: Iterable[str]) -> str:
    if platform == "lilith_os":
        return OWNER_CONSOLE
    if platform != "telegram":
        return PUBLIC
    owners = {str(i) for i in owner_telegram_ids if str(i).strip()}
    user = str(getattr(source, "user_id", "") or "")
    chat = str(getattr(source, "chat_id", "") or "")
    kind = str(getattr(source, "chat_type", "") or "").lower()
    if owners and user in owners and chat == user and kind in ("dm", "private"):
        return OWNER_TELEGRAM
    return PUBLIC


def load_settings(home: Any, *, owner_uid: int = 0) -> Optional[dict]:
    """The settings, or None (feature off) for a missing, foreign-owned, writable or malformed file."""
    path = Path(home) / "lilith_router" / SETTINGS_NAME
    try:
        meta = os.lstat(path)
        if not stat.S_ISREG(meta.st_mode) or meta.st_uid != owner_uid or meta.st_mode & 0o022 or meta.st_size > 4096:
            return None
        value = json.loads(path.read_text(encoding="ascii"))
    except (OSError, ValueError, UnicodeDecodeError):
        return None
    if not (isinstance(value, dict) and set(value) == _SETTINGS_FIELDS and value["schemaVersion"] == 1
            and value["enabled"] is True and isinstance(value["ownerTelegramUserIds"], list)
            and all(isinstance(i, str) and _TELEGRAM_ID.match(i) for i in value["ownerTelegramUserIds"])):
        return None
    return value


def _session(session_key: str) -> Optional[str]:
    session = re.sub(r"[^A-Za-z0-9._:-]", "_", str(session_key or ""))[:128]
    return session if session and _SESSION.match(session) else None


def turn_note(settings: Optional[dict], platform: str, source: Any, session_key: str, *, request=None,
              socket_path: str = None) -> Optional[str]:
    """The canonical-memory note for this turn, or None (feature off, service unavailable, nothing to say)."""
    _note.set(None)
    if not settings:
        return None
    session = _session(session_key)
    if session is None:
        return None
    channel = owner_channel(platform, source, settings["ownerTelegramUserIds"])
    if channel == PUBLIC:                  # owner decision 2026-11-06: no canonical memory at all outside the
        return None                        # owner channels (Discord, Telegram groups, other users, other platforms)
    try:
        payload = (request or _ctx.request_context)(socket_path or _ctx.DEFAULT_SOCKET,
                                                    channel=channel, session=session, timeout=DEFAULT_TIMEOUT)
        owner = channel != PUBLIC and isinstance(payload, dict) and payload.get("ownerChannel") is True
        note = _ctx.render_context_note(payload, include_personal=owner)
    except Exception:
        note = None
    _note.set(note)
    return note


def current_note() -> Optional[str]:
    return _note.get()


def _with_note(ephemeral: Optional[str], note: str) -> str:
    base = (ephemeral or "").strip()
    return note if not base else base + "\n\n" + note


def merge(result: Any, *, note: Optional[str], combined_ephemeral: Optional[str], session_key: str,
          cached_agent: Any) -> Any:
    """Add the note to the route's result. `None` stays `None` only when there is no note and the cached agent was not
    built with one; otherwise the main agent gets the note, rebuilt once whenever the note changed."""
    digest = hashlib.sha256(note.encode("utf-8")).hexdigest() if note else None
    if isinstance(result, dict) and "final_response" in result:
        return result                                     # a ready reply: no main-agent prompt to change
    built = _built_with.get(session_key)
    stale = cached_agent is not None and built != digest
    if digest is None and not stale:
        _built_with.pop(session_key, None)
        return result
    out = dict(result) if isinstance(result, dict) else {}
    base = out.get("combined_ephemeral", combined_ephemeral)
    out["combined_ephemeral"] = _with_note(base, note) if note else (base or "")
    if stale:
        out["force_rebuild"] = True
    if digest is None:
        _built_with.pop(session_key, None)
    else:
        _built_with[session_key] = digest
    return out
