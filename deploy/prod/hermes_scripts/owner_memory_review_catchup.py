#!/usr/bin/env python3
"""One-time catch-up for LILITH's nightly memory review (owner GO 2026-11-15). Read only, like the nightly script.

Between 2026-11-06 and 2026-11-15 the nightly review saw at most 26 hours at a time and proposed nothing after
2026-11-06, while one explicit durable statement ("Starlight Sessions") was never proposed. This prints the review
context for the owner's own conversations since 2026-11-06 00:00 Asia/Colombo (owner_memory_review.main(since=...):
bounded to 10 days, the same owner-only filter, active rows only, so forgotten or deactivated rows are never read),
with what is already remembered, waiting, rejected or replaced, so nothing is proposed twice.

Run it once as a one-shot Hermes cron job with the nightly review's own prompt: every proposal is staged by the memory
tool and waits for the owner's /memory approve; nothing is admitted. After EXPIRES it prints NO_NEW_OWNER_CONVERSATION,
so a stray rerun stays silent.
"""
import datetime as _dt
import importlib.util
import sys
import time
from pathlib import Path

WINDOW_START = _dt.datetime(2026, 11, 6, 0, 0, tzinfo=_dt.timezone(_dt.timedelta(hours=5, minutes=30)))
EXPIRES = _dt.datetime(2026, 11, 18, 0, 0, tzinfo=_dt.timezone(_dt.timedelta(hours=5, minutes=30)))


def _review():
    spec = importlib.util.spec_from_file_location(
        "owner_memory_review", Path(__file__).resolve().with_name("owner_memory_review.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def context(now: float = None, home: Path = None) -> str:
    now = time.time() if now is None else now
    if now >= EXPIRES.timestamp():
        return "NO_NEW_OWNER_CONVERSATION"
    review = _review()
    return review.main(home if home is not None else review.HOME, now=now, since=WINDOW_START.timestamp())


if __name__ == "__main__":
    sys.stdout.write(context() + "\n")
