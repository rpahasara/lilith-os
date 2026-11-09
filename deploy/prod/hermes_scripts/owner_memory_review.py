#!/usr/bin/env python3
"""Context for LILITH's nightly memory review (Hermes cron --script; stdout goes into the review prompt). Read only.

Prints the owner's own conversations of the last REVIEW_HOURS: the console (lilith_os), the owner's private
Telegram DM and the owner's verified Discord DM (fast Groq turns included: they are stored in state.db like every
other turn). The Discord DM counts only for a (user id, DM channel id) pair the owner verified through the Telegram
owner DM and the operator installed in canonical_memory.json `ownerDiscordDms` (the router's own owner rule). Plus
what is already
remembered, what is already waiting for approval and what the owner already rejected, so the review never proposes
the same thing twice. Nothing from any other chat is read. Prints NO_NEW_OWNER_CONVERSATION when there is nothing new.

P-4 (consolidation context v2, 2026-11-09): the review also sees WHICH moments mattered, from evidence LILITH already
has, never from a mood: an owner line is tagged when LILITH's own router trace (metadata only, owner turns) saw a durable
correction, a reported setback or progress, a tracked goal, or a question she could not ground; and tracked goals that
reached an outcome in the window are listed from the Goals store (read-only GET /os/goals). Plus wording guidance:
typed preferences / boundaries, dated event facts, fictional or test scenarios are never facts, at most 3 proposals.
Nothing new is stored; every proposal still needs the owner's approval.

Rejections leave no trace in Hermes (/memory reject deletes the pending file), so `snapshot()` (run every few minutes
by the silent no-agent cron job owner_memory_snapshot.py) records every pending proposal in SEEN; a recorded proposal
that is no longer pending and whose text is not in USER.md / MEMORY.md was rejected. The read is also a snapshot, so
it is the one place that writes (only SEEN, under ~/.hermes/memory-review/).
"""
import datetime as _dt
import glob
import json
import os
import re
import sqlite3
import urllib.request
import sys
import time
from pathlib import Path

HOME = Path(os.environ.get("HERMES_HOME") or Path.home() / ".hermes")
REVIEW_HOURS = 26
PER_MESSAGE = 700
TOTAL = 14000
SEEN = "memory-review/seen.jsonl"
API = os.environ.get("LILITH_OS_API_URL", "http://127.0.0.1:8765")


def owner_ids(home: Path) -> set:
    try:
        settings = json.loads((home / "lilith_router" / "canonical_memory.json").read_text(encoding="ascii"))
        return {str(i) for i in settings.get("ownerTelegramUserIds", []) if str(i).strip()}
    except (OSError, ValueError):
        return set()


def owner_discord_dms(home: Path) -> set:
    """Verified (Discord user id, DM channel id) pairs; empty when absent or malformed (fail closed)."""
    try:
        settings = json.loads((home / "lilith_router" / "canonical_memory.json").read_text(encoding="ascii"))
        pairs = settings.get("ownerDiscordDms", [])
        return {(str(p["userId"]), str(p["chatId"])) for p in pairs
                if isinstance(p, dict) and str(p.get("userId", "")).isdigit() and str(p.get("chatId", "")).isdigit()}
    except (OSError, ValueError, TypeError, KeyError, AttributeError):
        return set()


def owner_sessions(con: sqlite3.Connection, ids: set, discord_dms: set = frozenset()) -> list:
    out = []
    for sid, source, user, chat, kind in con.execute(
            "SELECT id, source, user_id, chat_id, chat_type FROM sessions"):
        if source == "lilith_os":
            out.append(sid)
        elif (source == "telegram" and ids and str(user or "") in ids and str(chat or "") == str(user or "")
              and str(kind or "").lower() in ("dm", "private")):
            out.append(sid)
        elif (source == "discord" and (str(user or ""), str(chat or "")) in discord_dms
              and str(kind or "").lower() == "dm"):
            out.append(sid)
    return out


# -- P-4: moments that mattered (router trace, metadata only) ------------------------------------------------------
MOMENT_LINK_S = 180          # a trace record belongs to the owner line it follows by at most this many seconds


def moments(home: Path, since: float) -> list:
    """(timestamp, label) for owner turns where LILITH's own router trace saw something worth learning from. Reads
    only allow-listed flags of decisions.log (owner-turn lanes); never text. Missing or unreadable log: none."""
    out = []
    for name in ("decisions.log.1", "decisions.log"):
        try:
            lines = (home / "lilith_router" / name).read_text(encoding="utf-8").splitlines()
        except OSError:
            continue
        for ln in lines:
            try:
                r = json.loads(ln)
                ts = float(r.get("ts") or 0)
            except (ValueError, TypeError, AttributeError):
                continue
            if ts < since:
                continue
            lane = r.get("lane")
            if lane == "social_preferences" and r.get("durable_correction"):
                out.append((ts, "a correction about how LILITH should behave"))
            elif lane == "appraisal":
                sig = r.get("signals") or []
                if "setback" in sig:
                    out.append((ts, "they reported a setback"))
                if "progress" in sig:
                    out.append((ts, "they reported progress or an achievement"))
                if "goal" in sig:
                    out.append((ts, "touches a goal they track"))
            elif lane == "metacognition" and r.get("recall_gap"):
                out.append((ts, "LILITH had nothing remembered about what they asked"))
    return sorted(out)


def _when(value):
    """Epoch seconds from an ISO-8601 string or a number, or None."""
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        pass
    try:
        d = _dt.datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return (d if d.tzinfo else d.replace(tzinfo=_dt.timezone.utc)).timestamp()
    except ValueError:
        return None


_FOLLOW_UP = re.compile(r"^\s*follow\s+up\s+on\s+application\s+\S+\s*[\u2014\u2013:-]?\s*", re.I)
_IDS = re.compile(r"\b(?:application|app|goal|task|ticket|draft)\s*#?\s*[0-9a-f-]{1,36}\b|#\s*\d+", re.I)


def _goal_topic(title) -> str:
    """Plain topic without internal ids or tracking labels (same rule as the router's appraisal.goal_topic)."""
    text = " ".join(str(title or "").split())
    m = _FOLLOW_UP.match(text)
    if m:
        rest = text[m.end():]
        text = ("their application for " + rest) if rest else "a job application they're following up on"
    text = " ".join(_IDS.sub("", text).split()).strip(" -:,\u2014\u2013")
    return text[:120] if re.search(r"[A-Za-z]{3,}", text) else ""


OUTCOME_FIELDS = (("COMPLETED", "completedAt", "completed"), ("FAILED", "failedAt", "failed"),
                  ("CANCELLED", "cancelledAt", "cancelled"), ("BLOCKED", "blockedAt", "became blocked"))


def _goals(query: str = "limit=200"):
    """Goals from the Goals store (read-only GET /os/goals), or None when it cannot be read."""
    try:
        with urllib.request.urlopen(API + "/os/goals?" + query, timeout=5) as resp:
            goals = json.loads(resp.read().decode("utf-8")).get("goals", [])
    except Exception:
        return None
    return [g for g in goals if isinstance(g, dict)] if isinstance(goals, list) else None


COMMITMENT_TYPES = ("commitment.once", "commitment.routine")


def goal_outcomes(since: float) -> list:
    """Their tracked LIFE goals that reached an outcome in the window. LILITH's own commitments are excluded: they
    are reported separately (commitment_status) and are never memories about them. Fail-open: none."""
    goals = _goals() or []
    out = []
    for g in goals:
        if str(g.get("type") or "").startswith("commitment."):
            continue
        for state, field, verb in OUTCOME_FIELDS:
            at = _when(g.get(field))
            if g.get("lifecycleState") == state and at is not None and at >= since:
                topic = _goal_topic(g.get("title"))
                if topic:
                    day = _dt.datetime.fromtimestamp(at, _dt.timezone.utc).strftime("%Y-%m-%d")
                    out.append(f"- {topic}: {verb} on {day} (recorded in their tracked goals)")
    return out[:10]


FAILED_WINDOW_S = 7 * 86400


def commitment_status(now: float, since: float) -> list:
    """LILITH's own scheduled commitments, from the scheduler evidence the commitment sync recorded in the Goals
    store (P4-4). Unresolved ones (missed now, or failed in the last 7 days) are listed with their due time and the
    recorded reason; kept ones are only counted. No delivery is claimed beyond what the scheduler recorded."""
    once = _goals("limit=200&type=commitment.once")
    if once is None:
        return ["(commitment records unavailable this time; say nothing about commitments)"]
    lines = []
    for g in once:
        title = " ".join(str(g.get("title") or "a scheduled reminder").split())[:80]
        due = g.get("deadline") or "unknown time"
        state = g.get("lifecycleState")
        if state == "BLOCKED":
            lines.append(f"- UNRESOLVED: \"{title}\" was due {due} and the scheduler has not run it "
                         f"({str(g.get('blockedReason') or 'missed')[:120]})")
        elif state == "FAILED" and (_when(g.get("failedAt")) or 0) >= now - FAILED_WINDOW_S:
            lines.append(f"- UNRESOLVED: \"{title}\" (due {due}): the scheduled run failed or its delivery "
                         "failed; it did not reach them as planned")
    kept = sum(1 for g in once if g.get("lifecycleState") == "COMPLETED" and (_when(g.get("completedAt")) or 0) >= since)
    if kept:
        lines.append(f"- {kept} reminder(s) ran as scheduled (scheduler run completed; whether each reached them "
                     "is not verified). Routine reminders: not memories, never propose them.")
    return lines or ["(none)"]


GUIDANCE = """\
- Propose at most 3 items, the ones most worth keeping. Fewer is fine; nothing is fine.
- A lasting preference or boundary about how LILITH talks or behaves: word it "Preference (scope): ..." or
  "Boundary (scope): ...", scope = global, casual, technical or topic: <word>.
- An achievement, setback or outcome worth remembering: a short dated fact in plain words ("On 2026-11-09 he passed
  ..."). Never record a mood or how LILITH felt about it.
- A fictional, hypothetical or test scenario is never a real fact about them. If they clarified that something was only
  a test or made up, you may propose a boundary to treat it that way; never store the scenario itself as true.
- If a new statement contradicts something already remembered, propose replacing that entry, not adding a second one.
- LILITH's own commitments (reminders, follow-ups she scheduled) are her responsibilities, not facts about them:
  never propose them as memories. An UNRESOLVED one is hers to own next time they talk; never say it was delivered.
- Lines tagged [moment: ...] are where LILITH's own signals saw something notable. They are hints, not proof: read
  the conversation itself before proposing anything."""


def conversation(con: sqlite3.Connection, sessions: list, since: float, marks_at: list = ()) -> list:
    if not sessions:
        return []
    cols = {r[1] for r in con.execute("PRAGMA table_info(messages)")}
    active = " AND coalesce(active, 1) != 0" if "active" in cols else ""
    marks = ",".join("?" * len(sessions))
    rows = con.execute(
        f"SELECT role, content, timestamp FROM messages WHERE session_id IN ({marks}) AND timestamp >= ?"
        f" AND role IN ('user', 'assistant'){active} ORDER BY timestamp, id", (*sessions, since)).fetchall()
    seen, lines = set(), []
    marks_at = list(marks_at or ())
    owner_ts = [ts for role, content, ts in rows if role == "user" and isinstance(content, str) and content.strip()]
    tags = {}
    for mts, label in marks_at:                # each moment goes to the latest owner line at or before it
        prior = [t for t in owner_ts if t <= mts + 5 and mts - t <= MOMENT_LINK_S]
        if prior:
            tags.setdefault(max(prior), [])
            if label not in tags[max(prior)]:
                tags[max(prior)].append(label)
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
        tag = (" [moment: " + "; ".join(tags[ts]) + "]") if role == "user" and ts in tags else ""
        lines.append(f"{'OWNER' if role == 'user' else 'LILITH'}: {text}{tag}")
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
        for r in new:                                  # L18: the proposal as a learning event (best effort)
            items = [{"store": o.get("target") or "user", "action": o.get("action"),
                      "text": o.get("content") or o.get("old_text")} for o in _operations(r)
                     if o.get("action") in ("add", "replace", "remove") and (o.get("content") or o.get("old_text"))]
            if items:
                try:
                    _api("POST", "/os/learning-events", {"kind": "PROPOSED", "proposal_id": str(r["id"]),
                                                         "items": items, "source": str(r.get("origin") or "hermes")})
                except Exception:
                    pass
    return len(new)


def _api(method: str, path: str, body=None):
    import urllib.request
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(API + path, data=data, method=method, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read().decode("utf-8"))


def l18_rejected() -> list:
    """Texts the owner rejected, from LILITH OS's L18 learning events (runtime independent); [] when unreachable."""
    try:
        return [e["text"] for e in _api("GET", "/os/learning-events?kind=REJECTED")["events"] if e.get("text")]
    except Exception:
        return []


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
    out += [f"- {t[:200]}" for t in l18_rejected() if _norm(t) not in memory]
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
    since = now - REVIEW_HOURS * 3600
    try:
        lines = conversation(con, owner_sessions(con, owner_ids(home), owner_discord_dms(home)), since,
                             moments(home, since))
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
        "=== HOW TO PROPOSE ===", GUIDANCE, "",
        f"=== THEIR TRACKED GOAL OUTCOMES, last {REVIEW_HOURS} h (verified in their goals; propose a dated fact "
        "only if it matters to them) ===", "\n".join(goal_outcomes(since)) or "(none)", "",
        "=== LILITH'S OWN COMMITMENTS (scheduler evidence; her responsibilities, NOT memories about them) ===",
        "\n".join(commitment_status(now, since)), "",
        f"=== OWNER CONVERSATION, last {REVIEW_HOURS} h (console + private Telegram DM + verified Discord DM) ===",
        *body,
    ])


if __name__ == "__main__":
    sys.stdout.write(main() + "\n")
