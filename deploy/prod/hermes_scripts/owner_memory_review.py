#!/usr/bin/env python3
"""Context for LILITH's nightly memory review (Hermes cron --script; stdout goes into the review prompt). Read only.

Prints the owner's own conversations of the last REVIEW_HOURS: the console (lilith_os) and the owner's private
Telegram DM (fast Groq turns included: they are stored in state.db like every other turn), plus what is already
remembered and what is already waiting for approval, so the review never proposes the same thing twice.
Nothing from any other chat is read. Prints NO_NEW_OWNER_CONVERSATION when there is nothing to review.
"""
import glob
import json
import os
import sqlite3
import sys
import time
from pathlib import Path

HOME = Path(os.environ.get("HERMES_HOME") or Path.home() / ".hermes")
REVIEW_HOURS = 26
PER_MESSAGE = 700
TOTAL = 14000


def owner_ids(home: Path) -> set:
    try:
        settings = json.loads((home / "lilith_router" / "canonical_memory.json").read_text(encoding="ascii"))
        return {str(i) for i in settings.get("ownerTelegramUserIds", []) if str(i).strip()}
    except (OSError, ValueError):
        return set()


def owner_sessions(con: sqlite3.Connection, ids: set) -> list:
    out = []
    for sid, source, user, chat, kind in con.execute(
            "SELECT id, source, user_id, chat_id, chat_type FROM sessions"):
        if source == "lilith_os":
            out.append(sid)
        elif (source == "telegram" and ids and str(user or "") in ids and str(chat or "") == str(user or "")
              and str(kind or "").lower() in ("dm", "private")):
            out.append(sid)
    return out


def conversation(con: sqlite3.Connection, sessions: list, since: float) -> list:
    if not sessions:
        return []
    cols = {r[1] for r in con.execute("PRAGMA table_info(messages)")}
    active = " AND coalesce(active, 1) != 0" if "active" in cols else ""
    marks = ",".join("?" * len(sessions))
    rows = con.execute(
        f"SELECT role, content, timestamp FROM messages WHERE session_id IN ({marks}) AND timestamp >= ?"
        f" AND role IN ('user', 'assistant'){active} ORDER BY timestamp, id", (*sessions, since)).fetchall()
    seen, lines = set(), []
    for role, content, ts in rows:
        if not isinstance(content, str) or not content.strip():
            continue
        key = (role, content.strip())
        if key in seen:                       # compaction can re-insert identical rows
            continue
        seen.add(key)
        text = " ".join(content.split())
        if len(text) > PER_MESSAGE:
            text = text[:PER_MESSAGE] + " ..."
        lines.append(f"{'OWNER' if role == 'user' else 'LILITH'}: {text}")
    return lines


def pending(home: Path) -> list:
    out = []
    for path in sorted(glob.glob(str(home / "pending" / "memory" / "*.json"))):
        try:
            rec = json.loads(Path(path).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        out.append(f"- {rec.get('id', Path(path).stem)}: {str(rec.get('summary', ''))[:200]}")
    return out


def remembered(home: Path) -> str:
    parts = []
    for name in ("USER.md", "MEMORY.md"):
        try:
            text = (home / "memories" / name).read_text(encoding="utf-8").strip()
        except OSError:
            text = ""
        parts.append(f"[{name}]\n{text or '(empty)'}")
    return "\n\n".join(parts)


def main(home: Path = HOME, now: float = None) -> str:
    now = time.time() if now is None else now
    try:
        con = sqlite3.connect(f"file:{home / 'state.db'}?mode=ro", uri=True, timeout=10)
    except sqlite3.Error:
        return "NO_NEW_OWNER_CONVERSATION"
    try:
        lines = conversation(con, owner_sessions(con, owner_ids(home)), now - REVIEW_HOURS * 3600)
    finally:
        con.close()
    if not any(l.startswith("OWNER: ") for l in lines):
        return "NO_NEW_OWNER_CONVERSATION"
    body, size = [], 0
    for line in reversed(lines):              # keep the most recent part when long
        if size + len(line) > TOTAL:
            break
        body.append(line)
        size += len(line) + 1
    body.reverse()
    return "\n".join([
        "=== ALREADY REMEMBERED (do not propose again) ===", remembered(home), "",
        "=== ALREADY WAITING FOR APPROVAL (do not propose again) ===", "\n".join(pending(home)) or "(none)", "",
        "=== ALSO STORED ELSEWHERE (never propose) ===",
        "- the project codename and the relationship-origin statement (canonical memory)", "",
        f"=== OWNER CONVERSATION, last {REVIEW_HOURS} h (console + private Telegram DM) ===", *body,
    ])


if __name__ == "__main__":
    sys.stdout.write(main() + "\n")
