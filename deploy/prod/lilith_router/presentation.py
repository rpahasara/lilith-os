"""Owner-facing presentation of Hermes conversation search (2026-11-15, Timeline replay finding).

1. Dates. Hermes' session_search tool formats every conversation date with ``datetime.fromtimestamp(ts)``, i.e. the
   host clock (UTC on PROD), not Hermes' configured timezone. A message sent 2026-10-19 21:00 UTC is 20 Oct 02:30 in
   Asia/Colombo, but the agent was shown "October 19" and told the owner so. ``install_session_search_dates`` replaces
   that one display formatter, in the running gateway only, with one that converts to Hermes' zone and names it.
   Message-level results carried only a raw epoch ``timestamp`` (left for the model to convert, as UTC); they now
   also carry ``when`` in Hermes' zone. The stored epoch timestamps, sorting and search are untouched: only what the
   agent reads changes.

2. Links. The same tool asks the model to paste ``@session:<profile>/<id>`` links into replies because the Hermes
   desktop renders them. Telegram, Discord and the LILITH console do not, so the owner saw a raw internal reference.
   ``strip_session_links`` removes every sentence carrying one from the final reply (the agent's own tool calls still
   use the ids; only the delivered text changes). If nothing else would remain, the references alone are removed.

Fail open: any error leaves Hermes' behaviour unchanged.
"""
from __future__ import annotations

import datetime as dt
import logging
import os
import re
import sys
from typing import Optional, Tuple

logger = logging.getLogger(__name__)

_FORMAT = "%B %d, %Y at %I:%M %p"
_MARK = "_lilith_zoned"


def _zone() -> Tuple[dt.tzinfo, str]:
    """Hermes' configured zone (hermes_time: HERMES_TIMEZONE, else config.yaml), else UTC. Always named."""
    try:
        import hermes_time  # the gateway's own resolver (env first, then config.yaml)
        tz = hermes_time.get_timezone()
        if tz is not None:
            return tz, getattr(tz, "key", None) or str(tz)
    except Exception:
        pass
    name = (os.environ.get("HERMES_TIMEZONE") or "").strip()
    if name:
        try:
            from zoneinfo import ZoneInfo
            return ZoneInfo(name), name
        except Exception:
            pass
    return dt.timezone.utc, "UTC"


def zoned_timestamp(ts) -> str:
    """Same contract as Hermes' ``_format_timestamp`` (epoch number or numeric string -> readable date; None ->
    "unknown"; anything else returned as is), but in Hermes' zone with the zone named."""
    if ts is None:
        return "unknown"
    try:
        if isinstance(ts, str):
            if not ts.replace(".", "").replace("-", "").isdigit():
                return ts
            ts = float(ts)
        if isinstance(ts, (int, float)) and not isinstance(ts, bool):
            tz, name = _zone()
            return dt.datetime.fromtimestamp(ts, tz).strftime(_FORMAT) + " (%s)" % name
    except Exception:
        logger.debug("lilith_router: zoned timestamp failed for %r", ts, exc_info=True)
    return str(ts)


setattr(zoned_timestamp, _MARK, True)


def _with_when(shape):
    """Wrap Hermes' ``_shape_message``: each returned message keeps its raw ``timestamp`` (epoch, untouched) and gains
    ``when``, the same instant as a readable date in Hermes' zone, so the model never converts an epoch itself."""
    def shaped(*args, **kwargs):
        entry = shape(*args, **kwargs)
        try:
            ts = entry.get("timestamp") if isinstance(entry, dict) else None
            if ts is not None and "when" not in entry:
                entry["when"] = zoned_timestamp(ts)
        except Exception:
            logger.debug("lilith_router: message date presentation failed", exc_info=True)
        return entry
    setattr(shaped, _MARK, True)
    shaped.__wrapped__ = shape
    return shaped


def install_session_search_dates(module=None) -> bool:
    """Point session_search's date presentation at Hermes' zone (idempotent). True when installed: the session-level
    formatter (``_format_timestamp``) is replaced and message-level results (``_shape_message``) gain a zoned ``when``."""
    try:
        mod = module if module is not None else sys.modules.get("tools.session_search_tool")
        if mod is None:
            import importlib
            mod = importlib.import_module("tools.session_search_tool")
        current = getattr(mod, "_format_timestamp", None)
        if current is None:
            return False
        if not getattr(current, _MARK, False):
            mod._format_timestamp = zoned_timestamp
        shape = getattr(mod, "_shape_message", None)
        if callable(shape) and not getattr(shape, _MARK, False):
            mod._shape_message = _with_when(shape)
        return True
    except Exception:
        logger.debug("lilith_router: session_search date presentation not installed", exc_info=True)
        return False


SESSION_LINK_RE = re.compile(r"`?@session:[A-Za-z0-9_.\-]+(?:/[A-Za-z0-9_.:\-]+)?`?")
_SENTENCE_RE = re.compile(r"(?<=[.!?])\s+")


def strip_session_links(text: Optional[str]) -> Optional[str]:
    """The reply without internal ``@session:`` references (see the module docstring). Unchanged when it has none."""
    if not isinstance(text, str) or "@session:" not in text:
        return text
    kept_lines = []
    for line in text.split("\n"):
        if "@session:" not in line:
            kept_lines.append(line)
            continue
        kept = [s for s in _SENTENCE_RE.split(line) if not SESSION_LINK_RE.search(s)]
        if kept:
            kept_lines.append(" ".join(kept))
    out = re.sub(r"\n{3,}", "\n\n", "\n".join(kept_lines)).strip()
    if out:
        return out
    out = re.sub(r"[ \t]{2,}", " ", SESSION_LINK_RE.sub("", text)).strip()
    return out or text                                   # never deliver an empty reply
