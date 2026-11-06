#!/usr/bin/env python3
"""Context for LILITH's nightly memory review (Hermes cron --script; stdout goes into the review prompt). Read only.

Prints the owner's own conversations of the last REVIEW_HOURS: the console (lilith_os) and the owner's private
Telegram DM (fast Groq turns included: they are stored in state.db like every other turn), plus what is already
remembered, what is already waiting for approval and what the owner already rejected, so the review never proposes
the same thing twice. Nothing from any other chat is read. Prints NO_NEW_OWNER_CONVERSATION when there is nothing new.

Rejections leave no trace in Hermes (/memory reject deletes the pending file), so `snapshot()` (run every few minutes
by the silent no-agent cron job owner_memory_snapshot.py) records every pending proposal in SEEN; a recorded proposal
that is no longer pending and whose text is not in USER.md / MEMORY.md was rejected. The read is also a snapshot, so
it is the one place that writes (only SEEN, under ~/.hermes/memory-review/).
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
SEEN = "memory-review/seen.jsonl"


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


def _pending_records(home: Path) -> list:
    out = []
    for path in sorted(glob.glob(str(home / "pending" / "memory" / "*.json"))):
        try:
            rec = json.loads(Path(path).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        rec.setdefault("id", Path(path).stem)
        out.append(rec)
    return out


def pending(home: Path) -> list:
    return [f"- {r['id']}: {str(r.get('summary', ''))[:200]}" for r in _pending_records(home)]


def _contents(rec: dict) -> list:
    """The texts a proposal would add (single write or batch)."""
    payload = rec.get("payload") or {}
    ops = payload.get("operations") if payload.get("action") == "batch" else [payload]
    return [str(o.get("content")) for o in ops or [] if isinstance(o, dict) and o.get("content")]


def _operations(rec: dict) -> list:
    """Each write a proposal would make: action, target store, old text, new text (for the World Model sync)."""
    payload = rec.get("payload") or {}
    target = payload.get("target")
    ops = payload.get("operations") if payload.get("action") == "batch" else [payload]
    return [{"action": o.get("action"), "target": o.get("target") or target, "old_text": o.get("old_text"),
             "content": o.get("content")} for o in ops or [] if isinstance(o, dict)]


def _norm(text: str) -> str:
    return " ".join(text.split()).lower()


def _read_seen(home: Path) -> list:
    try:
        lines = (home / SEEN).read_text(encoding="utf-8").splitlines()
    except OSError:
        return []
    out = []
    for line in lines:
        try:
            out.append(json.loads(line))
        except ValueError:
            pass
    return out


def snapshot(home: Path = HOME) -> int:
    """Record every pending proposal once (id + texts). Silent; returns how many were new."""
    seen = {r.get("id") for r in _read_seen(home)}
    new = [r for r in _pending_records(home) if r["id"] not in seen]
    if new:
        path = home / SEEN
        path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        with open(path, "a", encoding="utf-8") as f:
            for r in new:
                f.write(json.dumps({"id": r["id"], "summary": str(r.get("summary", ""))[:300],
                                    "contents": _contents(r), "ops": _operations(r)}, ensure_ascii=False) + "\n")
    return len(new)


def rejected(home: Path) -> list:
    """Texts of seen proposals that are gone from pending and never reached memory."""
    live = {r["id"] for r in _pending_records(home)}
    memory = _norm(remembered(home))
    out = []
    for rec in _read_seen(home):
        if rec.get("id") in live:
            continue
        out += [f"- {t[:200]}" for t in rec.get("contents") or [] if _norm(t) not in memory]
    try:                                               # logged by /memory reject itself (no snapshot gap)
        logged = [json.loads(l) for l in (home / "memory-review" / "rejected.jsonl").read_text(
            encoding="utf-8").splitlines() if l.strip()]
    except (OSError, ValueError):
        logged = []
    for rec in logged:
        out += [f"- {t[:200]}" for t in rec.get("contents") or [] if t and _norm(t) not in memory]
    return list(dict.fromkeys(out))


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
        snapshot(home)
    except OSError:
        pass
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
        "=== REJECTED BY THE OWNER (never propose these again) ===", "\n".join(rejected(home)) or "(none)", "",
        "=== ALSO STORED ELSEWHERE (never propose) ===",
        "- the project codename and the relationship-origin statement (canonical memory)", "",
        f"=== OWNER CONVERSATION, last {REVIEW_HOURS} h (console + private Telegram DM) ===", *body,
    ])


if __name__ == "__main__":
    sys.stdout.write(main() + "\n")
